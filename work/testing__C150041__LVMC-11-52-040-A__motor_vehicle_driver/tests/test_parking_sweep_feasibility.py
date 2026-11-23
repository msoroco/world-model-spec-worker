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

    def test_rotated_translated_road_has_same_footprint_result(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "rotated.xodr"
            path.write_text((ROOT / "diagnostic-road.xodr").read_text().replace(
                'x="-80" y="0" hdg="0"', 'x="30" y="-14" hdg="1.5707963267948966"'))
            result = candidate_angles(path)
            self.assertTrue(result["all_footprints_fit"])
            self.assertEqual(result["samples"],
                             candidate_angles(ROOT / "diagnostic-road.xodr")["samples"])

    def test_discontinuous_geometry_extent_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "extent.xodr"
            path.write_text((ROOT / "diagnostic-road.xodr").read_text().replace(
                'hdg="0" length="160"', 'hdg="0" length="150"'))
            with self.assertRaisesRegex(ValueError, "extent must agree"):
                candidate_angles(path)

    def test_shifted_lane_offset_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "offset.xodr"
            path.write_text((ROOT / "diagnostic-road.xodr").read_text().replace(
                '<laneOffset s="0" a="0"', '<laneOffset s="0" a="2"'))
            with self.assertRaisesRegex(ValueError, "one straight authored driving lane"):
                candidate_angles(path)


if __name__ == "__main__":
    unittest.main()
