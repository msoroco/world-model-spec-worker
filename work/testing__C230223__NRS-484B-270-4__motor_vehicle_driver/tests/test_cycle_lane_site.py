import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cycle_lane_site import construct
from cycle_lane_intersection import ASSIGNMENT


class CycleLaneSiteTests(unittest.TestCase):
    def site(self):
        return {"assignment_id": ASSIGNMENT, "map_id": "synthetic-map-only",
                "intersection_id": "junction-a", "cycle_lane_id": "cycle-lane-a",
                "cycle_lane_designated_for": "mixed_cycle",
                "designation_authority": "synthetic-test-only",
                "intersection_polygon": [[0, 0], [4, 0], [4, 4], [0, 4]],
                "cycle_lane_polygon": [[-3, 1], [5, 1], [5, 2], [-3, 2]],
                "route_candidates": {"overlap": [[-2, 1.5], [6, 1.5]],
                                     "ordinary": [[-2, 3], [6, 3]],
                                     "miss": [[-2, 5], [6, 5]]}}

    def run_construct(self, site, candidate, requested):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "site.json"
            p.write_text(json.dumps(site), encoding="utf-8")
            return construct(p, candidate, requested)

    def test_route_segment_overlaps_without_interior_waypoint(self):
        result = self.run_construct(self.site(), "overlap", True)
        self.assertTrue(result["route_centerline_overlaps_both"])
        self.assertTrue(result["route_crosses_intersection"])

    def test_ordinary_lane_crosses_intersection(self):
        result = self.run_construct(self.site(), "ordinary", False)
        self.assertFalse(result["route_centerline_overlaps_both"])
        self.assertFalse(result["route_crosses_designated_cycle_lane"])

    def test_cycle_lane_ends_before_intersection(self):
        site = self.site()
        site["cycle_lane_polygon"] = [[-3, 1], [-1, 1], [-1, 2], [-3, 2]]
        result = self.run_construct(site, "overlap", False)
        self.assertTrue(result["route_crosses_designated_cycle_lane"])
        self.assertFalse(result["route_centerline_overlaps_both"])

    def test_false_positive_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "requested"):
            self.run_construct(self.site(), "ordinary", True)

    def test_route_missing_intersection_rejected(self):
        with self.assertRaisesRegex(ValueError, "intersection"):
            self.run_construct(self.site(), "miss", False)

    def test_designation_authority_required(self):
        site = self.site()
        del site["designation_authority"]
        with self.assertRaisesRegex(ValueError, "authority"):
            self.run_construct(site, "overlap", True)


if __name__ == "__main__":
    unittest.main()
