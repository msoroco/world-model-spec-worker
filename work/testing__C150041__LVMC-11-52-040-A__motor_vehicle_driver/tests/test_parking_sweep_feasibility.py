"""The provisional angle range follows actual authored lane width."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_sweep_feasibility import candidate_angles


class SweepFeasibilityTests(unittest.TestCase):
    def test_fixture_lane_covers_endpoints_and_all_samples(self):
        result = candidate_angles(ROOT / "diagnostic-road.xodr")
        self.assertEqual([x["angle_deg"] for x in result["samples"]],
                         list(range(0, 91, 10)))
        self.assertTrue(result["all_footprints_fit"])
        self.assertFalse(result["source_reviewed_native_site"])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_narrower_lane_rejects_perpendicular_footprint(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "narrow.xodr"
            path.write_text((ROOT / "diagnostic-road.xodr").read_text().replace(
                'a="5" b="0"', 'a="3" b="0"'))
            result = candidate_angles(path)
            self.assertFalse(result["all_footprints_fit"])
            self.assertFalse(result["samples"][-1]["full_footprint_inside_authored_lane"])

    def test_nonconstant_width_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "varying.xodr"
            path.write_text((ROOT / "diagnostic-road.xodr").read_text().replace(
                'a="5" b="0"', 'a="5" b="1"'))
            with self.assertRaisesRegex(ValueError, "constant authored lane"):
                candidate_angles(path)


if __name__ == "__main__":
    unittest.main()
