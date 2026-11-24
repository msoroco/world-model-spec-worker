import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswalk_construction import build
from crosswalk_measurements import ASSIGNMENT_ID


class CrosswalkConstructionTests(unittest.TestCase):
    def site(self):
        return {"assignment_id": ASSIGNMENT_ID, "map_id": "synthetic-only",
                "junction_kind": "road_intersection", "alley_junction": False,
                "opposite_sidewalk_lateral_lines": [[[10, -3], [14, -3]], [[10, 3], [14, 3]]],
                "curb_or_traveled_edge_source": "synthetic-curb",
                "crosswalk_marking_source": "synthetic-markings",
                "marked_crosswalk_polygon": [[10, -3], [14, -3], [14, 3], [10, 3]],
                "road_y_bounds": [-3, 5], "lead_stop_center": [7, 0],
                "ego_start_center": [-10, 0], "pass_lane_y": 3.5,
                "combined_vehicle_half_width_m": 2.4,
                "pedestrian_start": [12, -4], "pedestrian_end": [12, 6]}

    def run_build(self, site, kind="unmarked", behavior="pass"):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "site.json"
            p.write_text(json.dumps(site), encoding="utf-8")
            return build(p, crosswalk_kind=kind, ego_behavior=behavior)

    def test_unmarked_crossing_and_pass_route_constructed(self):
        r = self.run_build(self.site())
        self.assertEqual(r["crosswalk_polygon"], [[10, -3], [14, -3], [14, 3], [10, 3]])
        self.assertGreater(r["ego_route"][-1][0], 14)

    def test_wait_route_remains_behind_lead(self):
        r = self.run_build(self.site(), behavior="wait")
        self.assertLess(r["ego_route"][-1][0], r["lead_stop_center"][0])

    def test_marked_source_path(self):
        r = self.run_build(self.site(), kind="marked")
        self.assertEqual(r["crosswalk_kind"], "marked")

    def test_missing_opposite_sidewalk_rejected(self):
        s = self.site()
        s["opposite_sidewalk_lateral_lines"] = []
        with self.assertRaisesRegex(ValueError, "opposite sidewalk"):
            self.run_build(s)

    def test_alley_junction_rejected(self):
        s = self.site()
        s["alley_junction"] = True
        with self.assertRaisesRegex(ValueError, "road intersection"):
            self.run_build(s)

    def test_inadequate_lateral_clearance_rejected(self):
        s = self.site()
        s["pass_lane_y"] = 1
        with self.assertRaisesRegex(ValueError, "clearance"):
            self.run_build(s)


if __name__ == "__main__":
    unittest.main()
