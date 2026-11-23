import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measured_comparison_audit import compare_receipts
from turn_trace_finalizer import ASSIGNMENT


class MeasuredComparisonTest(unittest.TestCase):
    def setUp(self):
        self.candidate = json.loads((Path(__file__).resolve().parents[1] /
                                     "candidates/comparison-audit.json").read_text())
        fixed = {kind: {"record_id": "fixture-" + kind, "sha256": kind}
                 for kind in ("cab_license", "jurisdiction", "designation_provisions")}
        self.near = self.make("near_stand", self.candidate["near_map_sha256"],
                              "near-trace", "near-seal", fixed)
        self.far = self.make("far_stand", self.candidate["far_map_sha256"],
                             "far-trace", "far-seal", fixed)

    @staticmethod
    def make(case, map_hash, trace_hash, seal_hash, context):
        case_id = ASSIGNMENT + "__" + case
        return {"format": "c150530-saved-source-audit-v1", "passed": True,
                "case_id": case_id, "frames": 700, "trace_sha256": trace_hash,
                "capture_seal_sha256": seal_hash,
                "physical_or_pixel_acceptance": False,
                "measurement": {"case_id": case_id, "map_sha256": map_hash,
                                "engineering_right_turn_observed": True,
                                "first_junction_road_id": 110, "receiving_road_id": 11,
                                "stand_departure_frame": 50,
                                "first_intersection_entry_frame": 150,
                                "first_intersection_exit_frame": 200,
                                "context_source_joins": copy.deepcopy(context)}}

    def test_declared_measured_comparison(self):
        result = compare_receipts(self.near, self.far, self.candidate)
        self.assertTrue(result["passed"])
        self.assertFalse(result["physical_or_legal_acceptance"])

    def test_changed_fixed_jurisdiction_rejected(self):
        self.far["measurement"]["context_source_joins"]["jurisdiction"]["sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "fixed reviewed context: jurisdiction"):
            compare_receipts(self.near, self.far, self.candidate)

    def test_duplicate_original_attempt_rejected(self):
        self.far["trace_sha256"] = self.near["trace_sha256"]
        with self.assertRaisesRegex(ValueError, "same original attempt"):
            compare_receipts(self.near, self.far, self.candidate)

    def test_wrong_receiving_road_rejected(self):
        self.far["measurement"]["receiving_road_id"] = 12
        with self.assertRaisesRegex(ValueError, "first junction or receiving road"):
            compare_receipts(self.near, self.far, self.candidate)

    def test_wrong_case_map_rejected(self):
        self.far["measurement"]["map_sha256"] = self.candidate["near_map_sha256"]
        with self.assertRaisesRegex(ValueError, "exact independent source audit"):
            compare_receipts(self.near, self.far, self.candidate)

    def test_changed_duration_rejected(self):
        self.far["frames"] = 650
        with self.assertRaisesRegex(ValueError, "fixed capture duration"):
            compare_receipts(self.near, self.far, self.candidate)


if __name__ == "__main__":
    unittest.main()
