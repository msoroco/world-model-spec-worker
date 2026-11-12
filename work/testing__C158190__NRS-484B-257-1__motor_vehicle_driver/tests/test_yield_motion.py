import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_controller import PREFIX, Stage
from yield_motion import apply_motion


class Actor:
    def __init__(self, x, y, speed=6):
        self.point = type('Point', (), {'x': x, 'y': y, 'z': 0})()
        self.velocity = type('Velocity', (), {'x': speed, 'y': 0, 'z': 0})()
        self.control = None

    def get_location(self):
        return self.point

    def get_velocity(self):
        return self.velocity

    def apply_control(self, command):
        self.control = command


class World:
    def get_map(self):
        return self

    def get_waypoint(self, point, project_to_road=False):
        assert project_to_road is False
        road_id = 158190 if point.x < -8 else (158192 if point.x < 8 else 158193)
        return type('Waypoint', (), {'road_id': road_id})()


class MotionTests(unittest.TestCase):
    @staticmethod
    def control_factory(**kwargs):
        return kwargs

    def test_approach_slows_with_through_traffic_and_no_slow_differs(self):
        ego, through = Actor(-20, -1.8), Actor(1.8, -30)
        world = World()
        base = {'ego': ego, 'through': through}
        slow = apply_motion(world, dict(base, stage=Stage(PREFIX+'yield_nearest_view_through_approaches')),
                            control_factory=self.control_factory)
        self.assertEqual(slow['ego_target_mps'], 2.)
        self.assertGreater(ego.control['brake'], 0)
        self.assertEqual(slow['through_target_mps'], 7.)
        self.assertGreater(through.control['throttle'], 0)
        fast = apply_motion(world, dict(base, stage=Stage(PREFIX+'yield_nearest_view_no_slow')),
                            control_factory=self.control_factory)
        self.assertEqual(fast['ego_target_mps'], 6.)
        self.assertEqual(ego.control['brake'], 0)

    def test_clear_road_and_entered_vehicle_clearance(self):
        ego = Actor(-20, -1.8)
        stage = Stage(PREFIX+'yield_nearest_view_clear')
        clear = apply_motion(World(), {'ego': ego, 'through': None, 'stage': stage},
                             control_factory=self.control_factory)
        self.assertEqual(clear['ego_target_mps'], 4.)
        entered = Actor(1.8, -4)
        occupied = apply_motion(World(), {'ego': ego, 'through': entered, 'stage': stage},
                                control_factory=self.control_factory)
        self.assertEqual(occupied['ego_target_mps'], 2.)
        entered.point.y = 13
        after = apply_motion(World(), {'ego': ego, 'through': entered, 'stage': stage},
                             control_factory=self.control_factory)
        self.assertEqual(after['ego_target_mps'], 4.)

    def test_rejects_ego_off_route(self):
        ego = Actor(-20, -1.8)
        world = World()
        world.get_waypoint = lambda *args, **kwargs: type('Waypoint', (), {'road_id': 99})()
        with self.assertRaisesRegex(ValueError, 'left the authored'):
            apply_motion(world, {'ego': ego, 'through': None,
                                 'stage': Stage(PREFIX+'yield_nearest_view_clear')},
                         control_factory=self.control_factory)
