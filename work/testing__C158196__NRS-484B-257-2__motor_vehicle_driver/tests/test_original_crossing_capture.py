import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("original_crossing_capture", ROOT / "original_crossing_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class Box:
    def get_world_vertices(self, transform):
        return [NS(x=transform.x+dx, y=transform.y+dy)
                for dx, dy in ((-1,-1),(-1,1),(1,-1),(1,1))*2]


class Actor:
    bounding_box = Box()

    def __init__(self, x, y, road, velocity):
        self.place = NS(x=x, y=y, road=road)
        self.velocity = NS(x=velocity, y=0, z=0)

    def get_transform(self):
        return self.place

    def get_location(self):
        return self.place

    def get_velocity(self):
        return self.velocity


class CaptureTests(unittest.TestCase):
    def test_original_sample_binds_bodies_lanes_and_signal(self):
        ego, other = Actor(0,0,7,2), Actor(5,0,8,4)
        native_map = NS(get_waypoint=lambda location:NS(road_id=location.road, lane_id=-1))
        world = NS(get_map=lambda:native_map)
        light = NS(get_affected_lane_waypoints=lambda:[NS(road_id=7, lane_id=-1)],
                   get_state=lambda:"Green")
        row = capture.sample(world, ego, other, light, NS(x=10,y=0), 10, 0.5, "7:-1", "8:-1")
        self.assertEqual(row["ego_lane_key"], "7:-1")
        self.assertEqual(row["other_lane_key"], "8:-1")
        self.assertEqual(len(row["ego_body_vertices_xy_m"]), 8)
        self.assertEqual(row["other_distance_to_conflict_m"], 5)
        self.assertTrue(row["signal_controls_ego"])
        light.get_affected_lane_waypoints = lambda:[NS(road_id=9,lane_id=-1)]
        self.assertFalse(capture.sample(world, ego, other, light, NS(x=10,y=0), 10, 0.5, "7:-1", "8:-1")["signal_controls_ego"])

    def test_same_lane_and_missing_body_rejected(self):
        ego, other = Actor(0,0,7,2), Actor(5,0,7,4)
        native_map = NS(get_waypoint=lambda location:NS(road_id=location.road, lane_id=-1))
        world = NS(get_map=lambda:native_map)
        light = NS(get_affected_lane_waypoints=lambda:[NS(road_id=7, lane_id=-1)],
                   get_state=lambda:"Green")
        with self.assertRaisesRegex(ValueError, "distinct lane"):
            capture.sample(world, ego, other, light, NS(x=10,y=0), 10, 0.5, "7:-1", "7:-1")
        ego.bounding_box = NS(get_world_vertices=lambda transform:[])
        with self.assertRaisesRegex(ValueError, "complete Native body"):
            capture.sample(world, ego, other, light, NS(x=10,y=0), 10, 0.5, "7:-1", "8:-1")


if __name__ == "__main__":
    unittest.main()
