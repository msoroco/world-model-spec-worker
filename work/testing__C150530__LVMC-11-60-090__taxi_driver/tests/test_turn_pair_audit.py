import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stand_route import make
from turn_pair_audit import compare_receipts
from turn_trace_finalizer import ASSIGNMENT


class TurnPairAuditTest(unittest.TestCase):
    def setUp(self):
        self.right_layout = make("near_stand")
        self.straight_layout = make("near_stand_straight")
        self.map_hash = hashlib.sha256((ROOT / "candidates/near_stand.xodr").read_bytes()).hexdigest()
        source = {name: {"record_id": "fixture-" + name, "sha256": name}
                  for name in ("cab_license", "stand_designation", "stand_marking",
                               "posted_notice", "jurisdiction", "designation_provisions")}
        self.right = self.receipt("near_stand", "right-trace", "right-seal", 110, 11, True, source)
        self.straight = self.receipt("near_stand_straight", "straight-trace", "straight-seal",
                                     120, 12, False, source)

    def receipt(self, case, trace, seal, junction, road, right_seen, source):
        case_id = ASSIGNMENT + "__" + case
        return {"format": "c150530-saved-source-audit-v1", "passed": True,
                "case_id": case_id, "frames": 700, "trace_sha256": trace,
                "capture_seal_sha256": seal, "physical_or_pixel_acceptance": False,
                "measurement": {"case_id": case_id, "map_sha256": self.map_hash,
                                "stand_departure_frame": 50,
                                "first_intersection_entry_frame": 150,
                                "first_intersection_exit_frame": 200,
                                "first_junction_road_id": junction,
                                "receiving_road_id": road,
                                "engineering_right_turn_observed": right_seen,
                                "context_source_joins": copy.deepcopy(source)}}

    def compare(self):
        return compare_receipts(self.right, self.straight, self.right_layout,
                                self.straight_layout, self.map_hash)

    def test_declared_pair_is_measured_and_source_bound(self):
        result = self.compare()
        self.assertTrue(result["passed"])
        self.assertFalse(result["physical_or_legal_acceptance"])

    def test_changed_stand_geometry_rejected(self):
        self.straight_layout["stand"]["center"][0] -= 1
        with self.assertRaisesRegex(ValueError, "fixed candidate geometry"):
            self.compare()

    def test_right_turn_in_straight_arm_rejected(self):
        self.straight["measurement"]["first_junction_road_id"] = 110
        with self.assertRaisesRegex(ValueError, "requested route"):
            self.compare()

    def test_changed_posted_notice_source_rejected(self):
        self.straight["measurement"]["context_source_joins"]["posted_notice"]["sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "fixed reviewed source: posted_notice"):
            self.compare()

    def test_duplicate_trace_rejected(self):
        self.straight["trace_sha256"] = self.right["trace_sha256"]
        with self.assertRaisesRegex(ValueError, "reused one original attempt"):
            self.compare()


if __name__ == "__main__":
    unittest.main()
