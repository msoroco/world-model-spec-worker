import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
for name in ("native_capture", "delivery_audit"):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    globals()[name] = module


class Adapter:
    def __init__(self, png, *, broken_frame=None):
        self.png = png
        self.index = -1
        self.broken_frame = broken_frame
        self.controls = []
        self.stopped = False
        self.closed = False

    def tick(self):
        self.index += 1
        frame = 100 + self.index + (1 if self.index == self.broken_frame else 0)
        return frame, self.index * 0.05

    def observe(self, frame):
        i = self.index
        return {"frame": frame, "person_actor_id": 5,
                "driver_speed_mps": 0 if 10 <= i < 110 else 2,
                "body_gap_m": max(1, 20 - i * .05),
                "person_in_path": i < 100, "person_clear": i >= 100,
                "contact": False, "precaution": i >= 100}

    def camera_png(self, camera, frame):
        return self.png

    def apply_control(self, control):
        self.controls.append(control)

    def emergency_stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class TestNativeCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        buf = io.BytesIO()
        Image.new("RGB", (1, 1), "white").save(buf, format="PNG")
        self.png = buf.getvalue()
        self.att = self.root / "att.json"
        self.cue = self.root / "cue.json"
        self.att.write_text(json.dumps({"person_actor_id": 5, "basis": "partially_blind",
                                       "issuer": "fixture", "source_sha256": "a" * 64}))
        self.cue.write_text(json.dumps({"person_actor_id": 5, "cue": "white_cane",
                                       "observation": "actually_carried", "observer_source": "fixture",
                                       "source_sha256": "b" * 64}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_original_capture_and_media_audit(self):
        adapter = Adapter(self.png)
        manifest = native_capture.capture(adapter, "white_full_stop_wait",
                                          self.root / "attempt", attestation=self.att, carried_cue=self.cue)
        self.assertTrue(adapter.stopped and adapter.closed)
        self.assertEqual(len(adapter.controls), 900)
        self.assertEqual(manifest["original_frame_count"], 900)
        self.assertEqual(adapter.controls[0]["brake"], 1.0)
        self.assertEqual(adapter.controls[101]["target_speed_mps"], 2.0)
        receipt = delivery_audit.audit(self.root / "attempt" / "saved-manifest.json",
                                        dimensions={camera: (1, 1) for camera in delivery_audit.CAMERAS})
        self.assertEqual(receipt["decoded_original_pngs"], 3600)
        camera = self.root / "attempt" / "front" / "00000100.png"
        camera.write_bytes(b"altered")
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            delivery_audit.audit(self.root / "attempt" / "saved-manifest.json",
                                 dimensions={name: (1, 1) for name in delivery_audit.CAMERAS})

    def test_discontinuous_frame_stops_and_closes(self):
        adapter = Adapter(self.png, broken_frame=3)
        with self.assertRaisesRegex(ValueError, "discontinuity"):
            native_capture.capture(adapter, "white_full_stop_wait", self.root / "attempt",
                                   attestation=self.att, carried_cue=self.cue)
        self.assertTrue(adapter.stopped and adapter.closed)

    def test_rejects_bad_cue_and_profile(self):
        self.assertEqual(len(self.png) > 8, True)
        with self.assertRaisesRegex(ValueError, "900"):
            native_capture.capture(Adapter(self.png), "white_full_stop_wait", self.root / "attempt",
                                   attestation=self.att, carried_cue=self.cue, frame_count=5)
        self.cue.write_text(json.dumps({"person_actor_id": 5, "cue": "red_tip_cane",
                                       "observation": "actually_carried", "observer_source": "fixture",
                                       "source_sha256": "b" * 64}))
        with self.assertRaisesRegex(ValueError, "actually carried cue"):
            native_capture.capture(Adapter(self.png), "white_full_stop_wait", self.root / "attempt",
                                   attestation=self.att, carried_cue=self.cue)


if __name__ == "__main__":
    unittest.main()
