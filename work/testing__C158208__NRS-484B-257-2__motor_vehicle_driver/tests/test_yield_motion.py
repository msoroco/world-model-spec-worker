import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_motion import apply_motion
from yield_stage import PREFIX, primary


class Vehicle:
    def __init__(self, x, y):
        self.point = NS(x=x, y=y, z=.25)
        self.bounding_box = NS(get_world_vertices=self.vertices)
        self.control = None

    def vertices(self, transform):
        return [NS(x=self.point.x + dx, y=self.point.y + dy, z=z)
                for dx, dy in ((-1,-1),(-1,1),(1,1),(1,-1)) for z in (0,1)]

    def get_transform(self):
        return None

    def get_location(self):
        return self.point

    def get_velocity(self):
        return NS(x=0, y=0, z=0)

    def apply_control(self, control):
        self.control = control


class MotionTests(unittest.TestCase):
    def world(self):
        def waypoint(point, project_to_road=False):
            road = 158208 if point.x < 0 else 158212
            return NS(road_id=road)
        return NS(get_map=lambda: NS(get_waypoint=waypoint))

    def test_other_occupancy_and_no_slow_targets_are_distinct(self):
        ego, other = Vehicle(-12, 1.8), Vehicle(1.8, -4)
        staging = {"ego": ego, "other": other, "stage": primary(PREFIX + "yield_other_inside"),
                   "reference_origin_xy_m": [-9, 1.8], "ego_forward_xy": [1, 0]}
        control = lambda **kwargs: kwargs
        command = apply_motion(self.world(), staging, 100, control_factory=control)
        self.assertEqual(command["ego_target_mps"], 2)
        self.assertEqual(command["other_target_mps"], 0)
        self.assertEqual(other.control["brake"], 0)
        staging["stage"] = primary(PREFIX + "yield_no_slow")
        self.assertEqual(apply_motion(self.world(), staging, 100,
                                      control_factory=control)["ego_target_mps"], 8)


if __name__ == "__main__":
    unittest.main()
