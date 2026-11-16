import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route_following import RouteFollower


def waypoint(x, y):
    return Obj(transform=Obj(location=Obj(x=x, y=y)))


class Vehicle:
    def __init__(self, x, y, yaw):
        self.pose = Obj(location=Obj(x=x, y=y), rotation=Obj(yaw=yaw))

    def get_transform(self):
        return self.pose


class RouteFollowerTests(unittest.TestCase):
    def test_measured_remaining_distance_and_turn_steering(self):
        follower = RouteFollower([waypoint(0, 0), waypoint(10, 0), waypoint(20, 0), waypoint(20, 10)])
        first = follower.step(Vehicle(5, 0, 0))
        self.assertAlmostEqual(first["distance_to_route_end_m"], 25)
        self.assertAlmostEqual(first["steering"], 0)
        turn = follower.step(Vehicle(20, 2, 0))
        self.assertAlmostEqual(turn["distance_to_route_end_m"], 8)
        self.assertGreater(turn["steering"], 0)

    def test_rejects_off_corridor_and_repeated_waypoint(self):
        with self.assertRaisesRegex(ValueError, "Repeated"):
            RouteFollower([waypoint(0, 0), waypoint(0, 0)])
        follower = RouteFollower([waypoint(0, 0), waypoint(20, 0)], max_deviation_m=2)
        with self.assertRaisesRegex(ValueError, "departed"):
            follower.step(Vehicle(5, 3, 0))


if __name__ == "__main__":
    unittest.main()
