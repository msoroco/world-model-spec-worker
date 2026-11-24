import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from barrier_route import ASSIGNMENT, construct, measure


class BarrierRouteTests(unittest.TestCase):
    def site(self):
        return {"assignment_id": ASSIGNMENT, "map_id": "synthetic-map",
                "highway_id": "road-a", "city_highway_status": "unresolved",
                "barrier_id": "barrier-a", "barrier_geometry_source": "synthetic-geometry",
                "barrier_rectangle": [4, -1, 6, 1], "road_y_bounds": [-5, 5],
                "ego_half_width_m": 1,
                "route_candidates": {"wide": [[0, 3], [10, 3]],
                                     "near": [[0, 2.2], [10, 2.2]],
                                     "collision": [[0, 0], [10, 0]],
                                     "offroad": [[0, 4.5], [10, 4.5]]}}

    def packet(self):
        packet = self.site()
        packet.update({"original_trace_id": "synthetic-only", "ego_actor_id": "car-a",
                       "driver_actor_id": "driver-a", "surrounding_conditions_source": "synthetic-conditions",
                       "frames": [{"time_s": i * .05, "speed_mps": 8,
                                   "ego_footprint_vertices": [[i, 2], [i + 2, 2], [i + 2, 4], [i, 4]],
                                   "barrier_contact": False} for i in range(3)]})
        return packet

    def run_json(self, value, func, *args):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "source.json"
            p.write_text(json.dumps(value), encoding="utf-8")
            return func(p, *args)

    def test_wide_and_near_routes_have_distinct_clearance(self):
        wide = self.run_json(self.site(), construct, "wide")
        near = self.run_json(self.site(), construct, "near")
        self.assertGreater(wide["minimum_planned_body_clearance_m"], near["minimum_planned_body_clearance_m"])
        self.assertGreaterEqual(near["minimum_planned_body_clearance_m"], 0)

    def test_collision_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "intersects barrier"):
            self.run_json(self.site(), construct, "collision")

    def test_offroad_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "road bounds"):
            self.run_json(self.site(), construct, "offroad")

    def test_barrier_source_required(self):
        site = self.site()
        del site["barrier_geometry_source"]
        with self.assertRaisesRegex(ValueError, "barrier"):
            self.run_json(site, construct, "wide")

    def test_original_distance_observed_without_legal_label(self):
        result = self.run_json(self.packet(), measure)
        self.assertEqual(len(result["observations"]), 3)
        self.assertEqual(result["city_highway_status"], "unresolved")
        self.assertNotIn("careless", result)

    def test_original_body_vertices_required(self):
        packet = self.packet()
        packet["frames"][1]["ego_footprint_vertices"] = []
        with self.assertRaisesRegex(ValueError, "footprint"):
            self.run_json(packet, measure)


if __name__ == "__main__":
    unittest.main()
