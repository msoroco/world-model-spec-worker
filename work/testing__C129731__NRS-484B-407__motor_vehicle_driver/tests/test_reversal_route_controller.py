import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reversal_route_controller import RouteFollower


def location(x, y, z):
    return Obj(x=x, y=y, z=z)


def route():
    return {"target_speed_mps": 5.0, "waypoints": [
        {"x": float(x), "y": 0.0, "z": 0.0, "road_id": 17, "lane_id": -1}
        for x in (0, 10, 20)]}


class Actor:
    def __init__(self):
        self.x = 0.0
        self.yaw = 0.0
        self.speed = 0.0
        self.controls = []

    def get_transform(self):
        return Obj(location=location(self.x, 0.0, 0.0),
                   rotation=Obj(yaw=self.yaw))

    def get_velocity(self):
        return Obj(length=lambda: self.speed)

    def apply_control(self, control):
        self.controls.append(control)


class RouteFollowerTests(unittest.TestCase):
    def setUp(self):
        self.map = Obj(get_waypoint=lambda point, project_to_road=False: Obj(
            road_id=17, lane_id=-1))
        self.control_factory = lambda **kwargs: kwargs

    def test_bounded_control_and_completion_brake(self):
        follower = RouteFollower(self.map, route(), location,
                                 self.control_factory)
        actor = Actor()
        self.assertEqual(follower.apply(actor), "following")
        self.assertLessEqual(actor.controls[-1]["throttle"], 0.5)
        self.assertEqual(actor.controls[-1]["brake"], 0.0)
        actor.x = 10.0
        actor.speed = 8.0
        self.assertEqual(follower.apply(actor), "following")
        self.assertGreater(actor.controls[-1]["brake"], 0.0)
        self.assertEqual(actor.controls[-1]["throttle"], 0.0)
        actor.x = 20.0
        self.assertEqual(follower.apply(actor), "complete")
        self.assertEqual(actor.controls[-1],
                         {"throttle": 0.0, "steer": 0.0, "brake": 1.0})

    def test_wrong_lane_and_nonfinite_motion_rejected(self):
        wrong = route()
        wrong["waypoints"][1]["lane_id"] = 3
        with self.assertRaisesRegex(ValueError, "loaded road lane"):
            RouteFollower(self.map, wrong, location, self.control_factory)
        follower = RouteFollower(self.map, route(), location,
                                 self.control_factory)
        actor = Actor()
        actor.speed = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            follower.apply(actor)
        self.assertEqual(actor.controls, [])

    def test_unsourced_speed_or_repeated_route_rejected(self):
        wrong = route()
        wrong["target_speed_mps"] = 20
        with self.assertRaisesRegex(ValueError, "bounded speed"):
            RouteFollower(self.map, wrong, location, self.control_factory)
        wrong = route()
        wrong["waypoints"][1]["x"] = 0.1
        with self.assertRaisesRegex(ValueError, "near-zero"):
            RouteFollower(self.map, wrong, location, self.control_factory)


if __name__ == "__main__":
    unittest.main()
