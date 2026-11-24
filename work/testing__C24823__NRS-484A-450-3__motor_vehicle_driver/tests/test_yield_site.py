import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_site import ASSIGNMENT, select_stop_reference


class YieldSiteTests(unittest.TestCase):
    def site(self):
        return {"assignment_id": ASSIGNMENT, "map_id": "synthetic-only",
                "control": "yield_sign", "yield_sign_id": "yield-a",
                "vehicle_type": "motor_vehicle", "ego_actor_id": "car-a",
                "intersecting_highway_id": "highway-a", "approach_roadway_id": "road-a",
                "stopping_required_for_safety": "unresolved",
                "nearest_crosswalk_position": None, "marked_stop_line_position": None,
                "intersecting_highway_boundary_x": 0,
                "approaching_traffic_points": [[2, 6]],
                "occluders": [[-4, 1, -3, 3]],
                "driver_viewpoint_candidates": [{"id": "far", "position": [-6, 0]},
                                                {"id": "near", "position": [-1, 0]}]}

    def run_select(self, site):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "site.json"
            p.write_text(json.dumps(site), encoding="utf-8")
            return select_stop_reference(p)

    def test_nearest_geometric_view_selected(self):
        r = self.run_select(self.site())
        self.assertEqual(r["reference_kind"], "nearest_point_with_geometric_view")
        self.assertEqual(r["selected_candidate_id"], "near")
        self.assertEqual(r["stopping_required_for_safety"], "unresolved")

    def test_crosswalk_precedes_other_references(self):
        site = self.site()
        site["nearest_crosswalk_position"] = [-5, 0]
        site["marked_stop_line_position"] = [-3, 0]
        self.assertEqual(self.run_select(site)["reference_kind"], "nearest_crosswalk")

    def test_stop_line_precedes_viewpoint(self):
        site = self.site()
        site["marked_stop_line_position"] = [-3, 0]
        self.assertEqual(self.run_select(site)["reference_kind"], "marked_stop_line")

    def test_no_view_rejected(self):
        site = self.site()
        site["occluders"] = [[-5, -1, 1, 5]]
        with self.assertRaisesRegex(ValueError, "unobstructed"):
            self.run_select(site)

    def test_missing_occluder_rejected(self):
        site = self.site()
        site["occluders"] = []
        with self.assertRaisesRegex(ValueError, "occluder"):
            self.run_select(site)

    def test_yield_sign_required(self):
        site = self.site()
        site["control"] = "stop_sign"
        with self.assertRaisesRegex(ValueError, "yield-sign"):
            self.run_select(site)


if __name__ == "__main__":
    unittest.main()
