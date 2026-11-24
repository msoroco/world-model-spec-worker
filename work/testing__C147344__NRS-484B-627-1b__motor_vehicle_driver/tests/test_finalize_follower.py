import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finalize_follower import finalize
from right_lane_measurement import ASSIGNMENT


class FollowerJoinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = ASSIGNMENT + "__slow_middle_no_immediate_follower"
        self.trace_path = self.root / "original-trace.json"
        self.relation_path = self.root / "original-relation.json"
        self.trace = {"assignment_id": ASSIGNMENT, "case_id": self.case,
            "original_trace_id": "diagnostic-source", "frames": [
                {"frame": i, "time_s": i * .05, "ego_speed_mps": 4.,
                 "follower_gap_m": 20., "follower_speed_mps": 7.,
                 "ego_lane_id": "middle", "rightmost_same_direction_lane_id": "right",
                 "follower_actor_id": "car-b", "follower_lane_id": "middle",
                 "passing_slower_vehicle_observed": False,
                 "same_direction_marked_lane_count": 3}
                for i in range(900)]}
        self.relation = {"case_id": self.case, "source_kind": "original_native_relation",
            "relation_basis_source": "independent-original-ordering-readback",
            "samples": [{"frame": i, "time_s": i * .05,
                         "follower_actor_id": "car-b", "immediately_behind": False}
                        for i in range(900)]}
        self.write()

    def write(self):
        self.trace_path.write_text(json.dumps(self.trace) + "\n")
        self.relation_path.write_text(json.dumps(self.relation) + "\n")
        self.trace_sha = hashlib.sha256(self.trace_path.read_bytes()).hexdigest()
        self.relation_sha = hashlib.sha256(self.relation_path.read_bytes()).hexdigest()

    def run_join(self):
        return finalize(self.trace_path, self.trace_sha, self.relation_path,
                        self.relation_sha, self.case)

    def test_same_lane_without_immediate_relation_remains_false(self):
        result = self.run_join()
        self.assertEqual(result["original_frame_count"], 900)
        self.assertTrue(result["observations"][0]["follower_in_ego_lane"])
        self.assertFalse(result["observations"][0]["follower_immediately_behind_in_ego_lane"])
        self.assertEqual(result["legal_impediment_and_pass_necessity"], "unresolved")

    def test_positive_relation_comes_from_separate_source(self):
        self.relation["samples"][1]["immediately_behind"] = True
        self.write()
        result = self.run_join()
        self.assertTrue(result["observations"][1]["follower_immediately_behind_in_ego_lane"])

    def test_rejects_changed_relation_bytes_and_frame(self):
        self.relation_path.write_text("{}")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self.run_join()
        self.relation["samples"][1]["frame"] = 2
        self.write()
        with self.assertRaisesRegex(ValueError, "identity/frame/time join"):
            self.run_join()

    def test_rejects_inline_unsealed_relation(self):
        self.trace["frames"][0]["follower_immediately_behind_readback"] = True
        self.write()
        with self.assertRaisesRegex(ValueError, "unsealed inline follower"):
            self.run_join()


if __name__ == "__main__":
    unittest.main()
