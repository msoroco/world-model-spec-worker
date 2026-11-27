import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
from statutory_comparison import audit


class StatutoryComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c135702-comparison-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.left = {"case_id": "left", "law_id": "NRS-484B-450-1k", "cell_id": "C135702",
                     "actor": "motor_vehicle_driver", "road_geometry_sha256": "road",
                     "camera_profile": "overview1080-capability", "duration_s": 30,
                     "rate_hz": 20, "passing_controller": "fixed", "activity_request": "park",
                     "placement_request": "opposite", "obstruction_kind_request": "physical_obstruction",
                     "exception_request": None, "source_gate_passed": True,
                     "source_gate_sha256": "left-source", "physical_acceptance_claimed": False,
                     "legal_acceptance_claimed": False}
        self.right = dict(self.left, case_id="right", source_gate_sha256="right-source")

    def paths(self):
        a, b = self.root / "a.json", self.root / "b.json"
        a.write_text(json.dumps(self.left) + "\n")
        b.write_text(json.dumps(self.right) + "\n")
        return a, b

    def test_each_axis(self):
        values = {"activity_request": "stop", "placement_request": "alongside",
                  "obstruction_kind_request": "excavation", "exception_request": "police_direction"}
        for axis, value in values.items():
            with self.subTest(axis=axis):
                self.right = dict(self.left, case_id="right", source_gate_sha256="right-source",
                                  **{axis: value})
                self.assertEqual(audit(*self.paths(), axis)["axis"], axis)

    def test_wrong_axis_or_second_difference_rejected(self):
        self.right["activity_request"] = "stand"
        self.right["placement_request"] = "alongside"
        with self.assertRaisesRegex(ValueError, "isolate"):
            audit(*self.paths(), "activity_request")

    def test_changed_fixed_or_missing_source_rejected(self):
        self.right["activity_request"] = "stop"
        self.right["duration_s"] = 29
        with self.assertRaisesRegex(ValueError, "Fixed"):
            audit(*self.paths(), "activity_request")
        self.right["duration_s"] = 30
        self.right["source_gate_sha256"] = None
        with self.assertRaisesRegex(ValueError, "source gate"):
            audit(*self.paths(), "activity_request")


if __name__ == "__main__":
    unittest.main()
