import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import ASSIGNMENT, PAIRS, audit
from sight_construction import MPH_15_MPS


def measured(suffix):
    speed = {"blocked_below": MPH_15_MPS - .4,
             "blocked_at": MPH_15_MPS,
             "blocked_above": MPH_15_MPS + .4}.get(suffix, MPH_15_MPS)
    return {"case_id": ASSIGNMENT + "__" + suffix, "map_hash": "a" * 64,
            "approach_frame_ids": [100, 101], "traversal_frame_ids": [102, 103],
            "blocked_rays": [] if suffix == "clear_at" else [[100, "west", "traffic_view"]],
            "through_designation": suffix == "through_blocked",
            "traffic_controlled": suffix == "controlled_blocked",
            "traversal_speed_min_mps": speed, "traversal_speed_max_mps": speed,
            "source_sha256": {"site_source_sha256": "b" * 64,
                              "boundary_source_sha256": "c" * 64}}


class ComparisonAuditTests(unittest.TestCase):
    def run_comparison(self, comparison_id, mutations=None):
        suffixes = PAIRS[comparison_id][0]
        values = {suffix: measured(suffix) for suffix in suffixes}
        if mutations:
            mutations(values)
        with patch("comparison_audit.verify", side_effect=lambda path, case: {
                "case_id": case,
                "measurement": copy.deepcopy(values[case.removeprefix(ASSIGNMENT + "__")]),
                "camera_capture": {"camera_frames": 900, "camera_images_decoded": 3600}}):
            return audit({suffix: Path('/synthetic') / suffix for suffix in suffixes},
                         comparison_id)

    def test_four_exact_comparisons(self):
        for ident in PAIRS:
            with self.subTest(ident=ident):
                receipt = self.run_comparison(ident)
                self.assertTrue(receipt["source_join_passed"])
                self.assertIsNone(receipt["legal_conclusion"])

    def test_rejects_fixed_source_and_frame_window_drift(self):
        with self.assertRaisesRegex(ValueError, "fixed comparison source changed"):
            self.run_comparison("sight_condition", lambda values:
                values["clear_at"]["source_sha256"].update(site_source_sha256="d" * 64))
        with self.assertRaisesRegex(ValueError, "frame windows differ"):
            self.run_comparison("through_exception", lambda values:
                values["through_blocked"].update(traversal_frame_ids=[104, 105]))

    def test_rejects_missing_speed_boundary_and_case_inventory(self):
        with self.assertRaisesRegex(ValueError, "below-at-above"):
            self.run_comparison("speed_boundary", lambda values:
                values["blocked_at"].update(traversal_speed_max_mps=MPH_15_MPS + .1))
        with self.assertRaisesRegex(ValueError, "attempt inventory"):
            audit({"blocked_at": Path('/synthetic')}, "speed_boundary")

    def test_rejects_saved_attempt_without_decoded_cameras(self):
        with patch("comparison_audit.verify", side_effect=lambda path, case: {
                "case_id": case, "measurement": measured(case.removeprefix(ASSIGNMENT + "__")),
                "camera_capture": "unverified"}):
            with self.assertRaisesRegex(ValueError, "four complete original cameras"):
                audit({suffix: Path('/synthetic') / suffix for suffix in
                       PAIRS["sight_condition"][0]}, "sight_condition")


if __name__ == '__main__':
    unittest.main()
