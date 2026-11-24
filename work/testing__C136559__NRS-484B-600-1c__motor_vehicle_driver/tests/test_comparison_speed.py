import copy
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from comparison_speed import audit_pair
import test_speed_source_review as fixture_module


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.base_root = root / "base"
        self.other_root = root / "other"
        self.base_root.mkdir()
        self.other_root.mkdir()
        self.fixture = fixture_module.OriginalSpeedReviewTests()
        _, self.base_inventory = self.fixture._attempt(self.base_root, speed=15)

    def alternative(self, name, **kwargs):
        _, inventory = self.fixture._attempt(self.other_root, suffix=name, **kwargs)
        return inventory

    def test_strict_speed_boundary(self):
        other = self.alternative("below", speed=12)
        result = audit_pair(self.base_root, self.base_inventory,
                            self.other_root, other, "below")
        self.assertTrue(result["fixed_source_checks_passed"])
        self.assertEqual(result["legal_applicability"], "unresolved")
        other = self.alternative("equal", speed=13.4112)
        self.assertEqual(audit_pair(self.base_root, self.base_inventory,
                         self.other_root, other, "equal")["alternative_governed_frames"], 900)

    def test_rejects_changed_fixed_roadway_source(self):
        other = self.alternative("below", speed=12)
        self.fixture._change(self.other_root, other, "posted_control",
                             "governed_segment_source", "different authority order")
        with self.assertRaisesRegex(ValueError, "fixed posted control"):
            audit_pair(self.base_root, self.base_inventory,
                       self.other_root, other, "below")

    def test_governed_portion_and_direction(self):
        other = self.alternative("outside_zone", speed=15)
        route = json.loads((self.other_root / "route_occupancy.json").read_text())
        route["samples"][450]["segment_id"] = "outside"
        self.fixture._change(self.other_root, other, "route_occupancy", "samples", route["samples"])
        self.assertEqual(audit_pair(self.base_root, self.base_inventory,
            self.other_root, other, "outside_zone")["alternative_governed_frames"], 899)
        other = self.alternative("opposite_direction", speed=15)
        route = json.loads((self.other_root / "route_occupancy.json").read_text())
        for sample in route["samples"]:
            sample["direction"] = "west"
        self.fixture._change(self.other_root, other, "route_occupancy", "samples", route["samples"])
        self.assertEqual(audit_pair(self.base_root, self.base_inventory,
            self.other_root, other, "opposite_direction")["alternative_governed_frames"], 0)

    def test_authority_units_visibility(self):
        other = self.alternative("non_authority_sign", speed=15)
        self.fixture._change(self.other_root, other, "posted_control", "public_authority_posted", False)
        self.assertEqual(audit_pair(self.base_root, self.base_inventory,
            self.other_root, other, "non_authority_sign")["alternative_governed_frames"], 0)
        other = self.alternative("metric_equivalent", speed=15, unit="km/h", rate=48.28032)
        self.assertTrue(audit_pair(self.base_root, self.base_inventory,
            self.other_root, other, "metric_equivalent")["fixed_source_checks_passed"])
        other = self.alternative("sign_not_in_view", speed=15)
        self.fixture._change(self.other_root, other, "posted_control", "sign_in_camera_view", False)
        self.fixture._change(self.other_root, other, "posted_control", "off_camera_reading_assumption_source", "original authority order")
        self.assertTrue(audit_pair(self.base_root, self.base_inventory,
            self.other_root, other, "sign_not_in_view")["fixed_source_checks_passed"])

    def test_rejects_stale_original_packet(self):
        other = self.alternative("below", speed=12)
        with (self.other_root / "posted_control.json").open("a") as stream:
            stream.write(" ")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            audit_pair(self.base_root, self.base_inventory,
                       self.other_root, other, "below")

    def test_rejects_changed_speed_in_authority_comparison(self):
        other = self.alternative("non_authority_sign", speed=12)
        self.fixture._change(self.other_root, other, "posted_control", "public_authority_posted", False)
        with self.assertRaisesRegex(ValueError, "fixed actual vehicle speed"):
            audit_pair(self.base_root, self.base_inventory,
                       self.other_root, other, "non_authority_sign")


if __name__ == "__main__":
    unittest.main()
