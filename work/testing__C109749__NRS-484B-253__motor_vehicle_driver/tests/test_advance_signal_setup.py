import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from advance_signal_setup import probe_waypoints, upstream_waypoint


class Waypoint:
    def __init__(self, x, *, lane=1, yaw=0, junction=False):
        self.transform = NS(location=NS(x=x, y=0.0), rotation=NS(yaw=yaw))
        self.road_id = 8
        self.lane_id = lane
        self.is_junction = junction

    def previous(self, distance):
        return [Waypoint(self.transform.location.x - distance, lane=2),
                Waypoint(self.transform.location.x - distance)]


class AdvanceSignalSetupTests(unittest.TestCase):
    def test_three_probe_spawns_are_same_lane_and_distinct(self):
        points = probe_waypoints(Waypoint(-20), approach_to_turn_m=20)
        self.assertEqual(list(points), [25.0, 30.48, 36.0])
        self.assertEqual([round(point.transform.location.x, 2) for point in points.values()],
                         [-25.0, -30.48, -36.0])
        self.assertTrue(all(point.lane_id == 1 for point in points.values()))

    def test_rejects_wrong_lane_and_short_approach(self):
        class OtherLane(Waypoint):
            def previous(self, distance):
                return [Waypoint(-distance, lane=2)]
        with self.assertRaisesRegex(ValueError, 'Same-lane'):
            upstream_waypoint(OtherLane(-20), additional_m=10)
        with self.assertRaisesRegex(ValueError, 'cannot start'):
            probe_waypoints(Waypoint(-20), approach_to_turn_m=30)


if __name__ == '__main__':
    unittest.main()
