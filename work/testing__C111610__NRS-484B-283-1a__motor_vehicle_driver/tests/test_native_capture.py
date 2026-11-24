import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from native_capture import capture
from saved_measurement import process
from test_saved_measurement import packet, SCENE


def png():
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), (20, 40, 60)).save(stream, format="PNG")
    return stream.getvalue()


class Adapter:
    def __init__(self, site_bytes, gap=False, camera_error=False):
        self.site_hash = hashlib.sha256(site_bytes).hexdigest()
        self.index = 0
        self.gap = gap
        self.camera_error = camera_error
        self.image = png()
    def source_attestation(self):
        return {"native_origin": True, "map_name": "SourceTown",
                "site_sha256": self.site_hash, "source_ref": "reviewed Native source fixture"}
    def tick(self):
        i = self.index
        self.index += 1
        frame = 1000 + i + (1 if self.gap and i == 1 else 0)
        images = {name: self.image for name in
                  ("overview", "approach", "reference_corner", "driver_reference")}
        if self.camera_error and i == 1:
            images.pop("approach")
        return {"native_frame": frame, "native_elapsed_s": 100 + i / 20,
                "ego": {"actor_id": 101, "classification": "motor_vehicle_driver",
                        "body_center_xy_m": [0, -2], "brake": True},
                "pedestrian": {"actor_id": 202, "classification": "pedestrian",
                               "body_center_xy_m": [1, 2]},
                "cameras": images}


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c111610-native-capture-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.site = self.root / "site-source.json"
        self.site.write_text(json.dumps(packet()) + "\n")
        self.exception = self.root / "exception-source.json"
        self.exception.write_text(json.dumps({"case_id": json.loads(SCENE.read_text())["case_id"],
                                              "status": "none_identified",
                                              "source_refs": ["review/exception-source.json"]}) + "\n")
        self.dims = {name: (2, 2) for name in
                     ("overview", "approach", "reference_corner", "driver_reference")}

    def run_capture(self, adapter, attempt_name="attempt"):
        return capture(adapter, SCENE, self.site, self.exception,
                       self.root / attempt_name, dimensions=self.dims)

    def test_600_original_frames_seal_and_saved_measurement(self):
        index = self.run_capture(Adapter(self.site.read_bytes()))
        self.assertFalse(index["physical_acceptance_claimed"])
        self.assertEqual(index["files"]["site"]["sha256"],
                         hashlib.sha256(self.site.read_bytes()).hexdigest())
        result = process(self.root / "attempt", SCENE, self.root / "measurement.json")
        self.assertEqual(result["frame_count"], 600)
        self.assertEqual(result["summary"]["crosswalk_and_destination_half_frames"], 600)
        frame_map = json.loads((self.root / "attempt/frame_map.json").read_text())
        self.assertEqual((frame_map[0]["native_frame"], frame_map[-1]["native_frame"]),
                         (1000, 1599))
        media = json.loads((self.root / "attempt/camera_manifest.json").read_text())
        self.assertEqual(len(media), 600)
        self.assertEqual(set(media[0]["views"]), set(self.dims))

    def test_rejects_original_frame_gap_and_camera_omission(self):
        with self.assertRaisesRegex(ValueError, "frame gap"):
            self.run_capture(Adapter(self.site.read_bytes(), gap=True), "attempt-gap")
        with self.assertRaisesRegex(ValueError, "four original camera"):
            self.run_capture(Adapter(self.site.read_bytes(), camera_error=True), "attempt-camera")

    def test_rejects_site_tamper_and_nonempty_attempt(self):
        adapter = Adapter(self.site.read_bytes())
        changed = packet()
        changed["survey_revision"] = "changed after attestation"
        self.site.write_text(json.dumps(changed) + "\n")
        with self.assertRaisesRegex(ValueError, "attestation mismatch"):
            self.run_capture(adapter)
        self.site.write_text(json.dumps(packet()) + "\n")
        attempt = self.root / "attempt"
        attempt.mkdir(exist_ok=True)
        (attempt / "old.txt").write_text("prior\n")
        with self.assertRaisesRegex(ValueError, "must be empty"):
            self.run_capture(Adapter(self.site.read_bytes()))


if __name__ == "__main__":
    unittest.main()
