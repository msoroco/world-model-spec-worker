import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_measurement import ASSIGNMENT
from native_capture import capture
from delivery_audit import audit


class FakeAdapter:
    native_attested = False

    def __init__(self, kind="driveway", x=1, missing_camera=False, map_change=False):
        self.kind, self.x = kind, x
        self.missing_camera, self.map_change = missing_camera, map_change
        self.map_bytes = b"<OpenDRIVE><road id='alley-1'/></OpenDRIVE>"
        self.index = 0
        self.cleaned = False
        self.braked = False

    def get_map_packet(self, case):
        return {"case_id": case, "source_kind": "original_native_geometry",
                "map_sha256": hashlib.sha256(self.map_bytes).hexdigest(),
                "highway_status": True, "cul_de_sac": False,
                "highway_source": "survey:connected-public-highway",
                "alley_classification_source": "survey:alley-definition",
                "cul_de_sac_source": "survey:through-end",
                "property_abutting_source": "survey:parcel-boundary", "property_id": "parcel-1",
                "driveway_ownership_source": "survey:parcel-access",
                "vehicular_use_source": "survey:vehicle-entry",
                "ego_vehicle_id": "ego", "access_kind": self.kind,
                "access_corridor_polygon_m": [[0, 0], [4, 0], [4, 5], [0, 5]]}

    def get_opendrive_bytes(self):
        if self.map_change and self.index >= 900:
            return self.map_bytes + b"changed"
        return self.map_bytes

    def start(self, case):
        self.case = case

    def tick(self):
        i = self.index
        self.index += 1
        return {"frame": i + 1000, "time_s": round(i * .05, 2)}

    def read_footprint(self, frame):
        i = frame - 1000
        x = self.x
        return {"frame": frame, "time_s": round(i * .05, 2), "vehicle_id": "ego",
                "polygon_m": [[x, 1], [x + 2, 1], [x + 2, 3], [x, 3]]}

    def read_activity(self, frame):
        i = frame - 1000
        return {"frame": frame, "time_s": round(i * .05, 2),
                "state": "parked" if i >= 100 else "approaching",
                "speed_mps": 0 if i >= 100 else 2}

    def read_cameras(self, frame):
        row = {"frame": frame, "time_s": round((frame - 1000) * .05, 2),
               "png": b"\x89PNG\r\n\x1a\nsource-shaped-payload"}
        return {name: row for name in (("front", "rear", "left") if self.missing_camera
                                        else ("front", "rear", "left", "right"))}

    def brake(self):
        self.braked = True

    def cleanup(self):
        self.cleaned = True


class CaptureTests(unittest.TestCase):
    def test_both_access_kinds_and_positions(self):
        for kind in ("driveway", "entrance"):
            for position, x, expected in (("overlap", 1, 4), ("clear", 5, 0)):
                with self.subTest(kind=kind, position=position), tempfile.TemporaryDirectory() as directory:
                    case = ASSIGNMENT + "__" + kind + "_" + position
                    adapter = FakeAdapter(kind, x)
                    output = Path(directory) / "attempt"
                    summary = capture(adapter, case, output)
                    self.assertEqual(summary["max_access_intrusion_area_m2"], expected)
                    self.assertEqual(summary["frame_count"], 900)
                    self.assertTrue(summary["diagnostic_fixture"])
                    self.assertEqual(summary["legal_blocking_judgment"], "unresolved")
                    self.assertTrue(adapter.braked and adapter.cleaned)
                    inventory = json.loads((output / "inventory.json").read_text())
                    self.assertEqual(set(inventory["media"]), {"front", "rear", "left", "right"})
                    self.assertEqual(hashlib.sha256((output / "road.xodr").read_bytes()).hexdigest(),
                                     inventory["map_sha256"])
                    saved = audit(output, case, require_original=False)
                    self.assertEqual(saved["frame_count"], 900)
                    self.assertFalse(saved["physical_completion"])
                    with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                        audit(output, case)

    def test_saved_audit_rejects_mutated_camera_and_map(self):
        with tempfile.TemporaryDirectory() as directory:
            case = ASSIGNMENT + "__driveway_overlap"
            output = Path(directory) / "attempt"
            capture(FakeAdapter(), case, output)
            camera = output / "front.zip"
            camera.write_bytes(camera.read_bytes() + b"mutation")
            with self.assertRaisesRegex(ValueError, "camera archive changed"):
                audit(output, case, require_original=False)
            capture_output = Path(directory) / "second"
            capture(FakeAdapter(), case, capture_output)
            (capture_output / "road.xodr").write_bytes(b"different map")
            with self.assertRaisesRegex(ValueError, "map hash changed"):
                audit(capture_output, case, require_original=False)

    def test_rejects_missing_camera_and_map_mutation(self):
        for adapter, expected in ((FakeAdapter(missing_camera=True), "four original"),
                                  (FakeAdapter(map_change=True), "map changed")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, expected):
                    capture(adapter, ASSIGNMENT + "__driveway_overlap", Path(directory) / "attempt")
                self.assertFalse((Path(directory) / "attempt").exists())
                self.assertTrue(adapter.braked and adapter.cleaned)

    def test_rejects_wrong_case_and_access_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unknown exact"):
                capture(FakeAdapter(), ASSIGNMENT + "__other", Path(directory) / "attempt")
            with self.assertRaisesRegex(ValueError, "access kind differs"):
                capture(FakeAdapter(kind="entrance"), ASSIGNMENT + "__driveway_clear",
                        Path(directory) / "attempt")


if __name__ == "__main__":
    unittest.main()
