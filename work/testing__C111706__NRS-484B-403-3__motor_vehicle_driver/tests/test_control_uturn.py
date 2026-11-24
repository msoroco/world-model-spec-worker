import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from control_uturn import ControlError, RouteFollower, TimedOtherVehicle, validate_route


def route():
    return [
        {"x": 0.0, "y": 0.0, "road_id": 7, "lane_id": 1, "target_speed_mps": 3.0},
        {"x": 2.0, "y": 0.0, "road_id": 7, "lane_id": 1, "target_speed_mps": 3.0},
        {"x": 2.0, "y": 2.0, "road_id": 7, "lane_id": -1, "target_speed_mps": 2.0},
        {"x": 0.0, "y": 2.0, "road_id": 7, "lane_id": -1, "target_speed_mps": 2.0},
    ]


class Actor:
    def __init__(self, x=0.0, y=0.0, yaw=0.0, speed=0.0):
        self.x, self.y, self.yaw, self.speed = x, y, yaw, speed
        self.controls = []

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=self.y),
                               rotation=SimpleNamespace(yaw=self.yaw))

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0)

    def apply_control(self, control):
        self.controls.append(control)


class RouteControlTest(unittest.TestCase):
    @staticmethod
    def factory(**fields):
        return fields

    def test_turn_direction_and_actual_progression(self):
        follower = RouteFollower(route(), self.factory)
        actor = Actor()
        follower(actor, 0)
        self.assertEqual(follower.index, 1)
        self.assertGreater(actor.controls[-1]["throttle"], 0)
        actor.x = 2
        follower(actor, 1)
        self.assertEqual(follower.index, 2)
        self.assertGreater(actor.controls[-1]["steer"], 0)
        actor.y, actor.yaw = 2, 90
        follower(actor, 2)
        self.assertEqual(follower.index, 3)
        self.assertGreater(actor.controls[-1]["steer"], 0)
        actor.x, actor.y, actor.yaw = 0, 2, 180
        follower(actor, 3)
        self.assertTrue(follower.finished)
        self.assertEqual(actor.controls[-1]["brake"], 1)

    def test_no_skip_across_hairpin_and_loss_rejected(self):
        follower = RouteFollower(route(), self.factory)
        actor = Actor(x=0, y=6)
        with self.assertRaisesRegex(ControlError, "route tracking lost"):
            follower(actor, 0)
        self.assertEqual(follower.index, 1)

    def test_speed_above_target_brakes(self):
        follower = RouteFollower(route(), self.factory)
        actor = Actor(speed=6)
        follower(actor, 0)
        self.assertEqual(actor.controls[-1]["throttle"], 0)
        self.assertGreater(actor.controls[-1]["brake"], 0)

    def test_other_vehicle_timing_preserves_path_and_gains(self):
        near = TimedOtherVehicle(RouteFollower(route(), self.factory), 0)
        far = TimedOtherVehicle(RouteFollower(route(), self.factory), 80)
        near_actor, far_actor = Actor(), Actor()
        near(near_actor, 0)
        far(far_actor, 0)
        self.assertGreater(near_actor.controls[-1]["throttle"], 0)
        self.assertEqual(far_actor.controls[-1]["brake"], 1)
        far(far_actor, 80)
        self.assertEqual(far_actor.controls[-1], near_actor.controls[-1])

    def test_rejects_route_discontinuity_and_nan(self):
        points = route()
        points[2]["x"] = 50
        with self.assertRaisesRegex(ControlError, "disconnected"):
            validate_route(points)
        points = route()
        points[1]["target_speed_mps"] = math.nan
        with self.assertRaisesRegex(ControlError, "finite"):
            validate_route(points)

    def test_rejects_bad_start_road_and_start_time(self):
        with self.assertRaisesRegex(ControlError, "starting road"):
            validate_route(route(), expected_start_road=8)
        with self.assertRaisesRegex(ControlError, "start tick"):
            TimedOtherVehicle(RouteFollower(route(), self.factory), 901)
