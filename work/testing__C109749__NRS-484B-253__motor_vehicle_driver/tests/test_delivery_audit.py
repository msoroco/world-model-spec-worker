import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from delivery_audit import audit
from native_acquisition import capture
from saved_left_turn import ASSIGNMENT_ID
from test_native_acquisition import Adapter, waypoint


class DeliveryAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.case = ASSIGNMENT_ID + "__inside_yield"
        packet = {"map_sha256": "a" * 64, "source_ref": "diagnostic-map",
                  "junction_id": 9,
                  "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                  "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                  "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                  "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other"}
        source = self.root / "map.json"
        source.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        self.attempt = self.root / "attempt"
        capture(adapter=Adapter(), case_id=self.case, map_path=source,
                output=self.attempt, frame_count=2)
        receipt = json.loads((self.attempt / "acquisition-receipt.json").read_text())
        ids = {"ego": 11, "initial_opponent": 12}
        self.physical = {"case_id": self.case, "trace_sha256": receipt["trace_sha256"],
                         "map_sha256": receipt["map_sha256"], "maneuver_completed": True,
                         "completion_status": "met", "method": "synthetic fixture event test",
                         "reviewer": "CPU test", "original_frame_interval": [100, 101],
                         "participant_actor_ids": dict(ids)}
        self.pixel = {"case_id": self.case, "frame_map_sha256": receipt["frame_map_sha256"],
                      "receipt_sha256": self.hash(self.attempt / "acquisition-receipt.json"),
                      "reviewed_frame_count": 2,
                      "reviewed_cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                      "visible_actor_ids": dict(ids), "intersection_boundary_visible": True,
                      "full_duration_reviewed": True, "method": "synthetic fixture review test",
                      "reviewer": "CPU test"}
        self.physical_path = self.root / "physical.json"
        self.pixel_path = self.root / "pixel.json"
        self.write_reviews()

    @staticmethod
    def hash(path):
        import hashlib
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_reviews(self):
        self.physical_path.write_text(json.dumps(self.physical) + "\n")
        self.pixel_path.write_text(json.dumps(self.pixel) + "\n")

    def run_audit(self, allow_diagnostic=True):
        return audit(attempt=self.attempt, case_id=self.case,
                     physical_review=self.physical_path, pixel_review=self.pixel_path,
                     allow_diagnostic=allow_diagnostic)

    def test_software_positive_remains_unaccepted(self):
        report = self.run_audit()
        self.assertTrue(report["software_checks_passed"])
        self.assertTrue(report["diagnostic_fixture"])
        self.assertEqual(report["canonical_delivery_acceptance"], "unverified")

    def test_default_rejects_diagnostic(self):
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            self.run_audit(allow_diagnostic=False)

    def test_rejects_missing_actor_and_pixel_review(self):
        self.pixel["visible_actor_ids"].pop("initial_opponent")
        self.write_reviews()
        with self.assertRaisesRegex(ValueError, "required actor"):
            self.run_audit()
        self.pixel["visible_actor_ids"]["initial_opponent"] = 12
        self.pixel["full_duration_reviewed"] = False
        self.write_reviews()
        with self.assertRaisesRegex(ValueError, "visibility review incomplete"):
            self.run_audit()

    def test_rejects_stale_physical_and_incomplete_motion(self):
        self.physical["trace_sha256"] = "0" * 64
        self.write_reviews()
        with self.assertRaisesRegex(ValueError, "physical review is stale"):
            self.run_audit()
        self.physical["trace_sha256"] = json.loads((self.attempt / "acquisition-receipt.json").read_text())["trace_sha256"]
        self.physical["maneuver_completed"] = False
        self.write_reviews()
        with self.assertRaisesRegex(ValueError, "maneuver completion absent"):
            self.run_audit()

    def test_rejects_changed_original_pixels(self):
        image = self.attempt / "original-frames/000000100-overview.png"
        image.write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "camera source missing or changed"):
            self.run_audit()


if __name__ == "__main__":
    unittest.main()
