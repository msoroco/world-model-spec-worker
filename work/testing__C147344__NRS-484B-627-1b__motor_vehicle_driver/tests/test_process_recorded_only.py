"""Saved-only positive and missing-source CPU checks."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from process_recorded_only import process
from reviewed_scene import ASSIGNMENT


class SavedOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.attempt = self.root / "attempt"
        self.attempt.mkdir()
        self.case = ASSIGNMENT + "__slow_middle_follower"
        trace = {"assignment_id": ASSIGNMENT, "case_id": self.case,
                 "original_trace_id": "synthetic-fixture", "diagnostic_fixture": True,
                 "frames": [{"frame": i, "time_s": i / 20, "ego_speed_mps": 5.0,
                             "follower_gap_m": 20.0, "follower_speed_mps": 8.0,
                             "ego_lane_id": "-2", "rightmost_same_direction_lane_id": "-1",
                             "follower_actor_id": "b", "follower_lane_id": "-2",
                             "passing_slower_vehicle_observed": False,
                             "same_direction_marked_lane_count": 2} for i in range(900)]}
        relation = {"case_id": self.case, "source_kind": "original_native_relation",
                    "relation_basis_source": "synthetic fixture", "samples": [
                        {"frame": i, "time_s": i / 20, "follower_actor_id": "b",
                         "immediately_behind": True} for i in range(900)]}
        (self.attempt / "trace.json").write_text(json.dumps(trace) + "\n")
        (self.attempt / "relation.json").write_text(json.dumps(relation) + "\n")

    def test_positive_saved_only_leaves_acquisition_unchanged(self):
        before = {path.name: path.read_bytes() for path in self.attempt.iterdir()}
        receipt = process(self.attempt, self.root / "derived", self.case, diagnostic_fixture=True)
        self.assertEqual(receipt["original_frame_count"], 900)
        self.assertEqual(receipt["source_kind"], "synthetic_software_fixture")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.attempt.iterdir()})
        with self.assertRaisesRegex(ValueError, "fresh derived"):
            process(self.attempt, self.root / "derived", self.case, diagnostic_fixture=True)

    def test_original_mode_rejects_synthetic_and_missing_relation(self):
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            process(self.attempt, self.root / "derived", self.case)
        (self.attempt / "relation.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: relation.json"):
            process(self.attempt, self.root / "derived", self.case, diagnostic_fixture=True)


if __name__ == "__main__":
    unittest.main()
