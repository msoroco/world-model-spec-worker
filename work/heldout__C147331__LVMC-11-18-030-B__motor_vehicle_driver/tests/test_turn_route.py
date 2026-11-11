import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_route import select_marked_left_turn


class Waypoint:
    def __init__(self, x, y, yaw, *, road=1, lane=1, junction=False, marked=True):
        self.road_id, self.lane_id = road, lane
        self.is_junction, self.lane_type = junction, "Driving"
        marking = SimpleNamespace(type="Solid" if marked else "None")
        self.left_lane_marking = self.right_lane_marking = marking
        self.transform = SimpleNamespace(
            location=SimpleNamespace(x=x, y=y),
            get_forward_vector=lambda: SimpleNamespace(x=math.cos(math.radians(yaw)),
                                                       y=math.sin(math.radians(yaw))))
        self._next = []

    def next(self, _):
        return self._next


class Map:
    def __init__(self, starts):
        self.starts = starts

    def generate_waypoints(self, _):
        return self.starts


class TurnRouteTest(unittest.TestCase):
    def route(self, exit_yaw, *, marked=True):
        chain = [Waypoint(i * 2, 0, 0) for i in range(5)]
        junction = Waypoint(10, 0, 0, junction=True)
        exit_wp = Waypoint(10, 8, exit_yaw, road=2, marked=marked)
        for a, b in zip(chain, chain[1:]):
            a._next = [b]
        chain[-1]._next = [junction]
        junction._next = [exit_wp]
        return Map([chain[0]])

    def test_selects_connected_leftward_exit(self):
        selected = select_marked_left_turn(self.route(90))
        self.assertEqual(selected["approach_road_id"], 1)
        self.assertEqual(selected["exit_road_id"], 2)
        self.assertEqual(selected["requested_heading_change_deg"], 90)
        self.assertEqual(len(selected["approach"]), 5)

    def test_rejects_right_and_unmarked_exit(self):
        with self.assertRaisesRegex(ValueError, "No connected"):
            select_marked_left_turn(self.route(-90))
        with self.assertRaisesRegex(ValueError, "No connected"):
            select_marked_left_turn(self.route(90, marked=False))


if __name__ == "__main__":
    unittest.main()
