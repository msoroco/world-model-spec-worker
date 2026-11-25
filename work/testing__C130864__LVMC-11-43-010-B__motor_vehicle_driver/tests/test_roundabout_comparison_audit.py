import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from roundabout_comparison_audit import PAIRS, compare
from roundabout_measurements import ASSIGNMENT_ID


class ComparisonTests(unittest.TestCase):
    def packet(self, suffix):
        adjacent = suffix.startswith("adjacent")
        wider = "gap" in suffix
        wait = suffix.endswith("wait")
        return {"map_sha256": "a" * 64, "map_name": "reviewed-map",
                "jurisdiction_source": "source", "roundabout_geometry_source": "source",
                "circulating_surface_polygon": [[0, 0], [1, 0], [1, 1]],
                "entry_conflict_polygon": [[0, 0], [1, 0], [1, 1]],
                "circulating_lanes": [{"lane_id": "outer"}, {"lane_id": "inner"}],
                "ego_entry_lane": {"lane_id": "entry", "connected_circulating_lane_id": "outer"},
                "entry_line": [[0, 0], [1, 0]], "ego_blueprint": "vehicle.ego",
                "opponent_blueprint": "vehicle.other", "ego_spawn": {"x": 0},
                "ego_route": [{"x": 0}], "ego_release_tick": 700 if wait else 20,
                "opponent_release_tick": 0,
                "opponent_route": {"circulating_lane_id": "inner" if adjacent else "outer"},
                "opponent_spawn": {"x": 5 if wider else 1, "y": 1 if adjacent else 0},
                "opponent_points": [{"x": 5 if wider else 1, "y": 1 if adjacent else 0}]}

    def audit(self, suffix):
        return {"case_id": ASSIGNMENT_ID + "__" + suffix, "decoded_images": 3600,
                "motion": {"source_bindings": {"original_trace_sha256": suffix},
                           "first_observed_ego_entry_frame": 100}}

    def test_all_five_declared_comparisons(self):
        for comparison_id, (left, right, _) in PAIRS.items():
            with self.subTest(comparison_id=comparison_id):
                result = compare(comparison_id, self.audit(left), self.audit(right),
                                 self.packet(left), self.packet(right))
                self.assertTrue(result["source_bound"])
                self.assertIsNone(result["legal_verdict"])

    def test_rejects_fixed_map_and_duplicate_attempt(self):
        first = self.packet("connected_wait")
        second = self.packet("connected_enter")
        changed = copy.deepcopy(second)
        changed["map_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "fixed comparison source"):
            compare("connected_entry", self.audit("connected_wait"),
                    self.audit("connected_enter"), first, changed)
        duplicate = self.audit("connected_enter")
        duplicate["motion"]["source_bindings"]["original_trace_sha256"] = "connected_wait"
        with self.assertRaisesRegex(ValueError, "distinct original Native traces"):
            compare("connected_entry", self.audit("connected_wait"), duplicate, first, second)


if __name__ == "__main__":
    unittest.main()
