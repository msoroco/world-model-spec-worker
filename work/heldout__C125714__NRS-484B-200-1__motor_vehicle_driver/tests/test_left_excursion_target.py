from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from left_excursion_target import pinned_subject_waypoint, target_xy


def waypoint(x_direction):
    location = SimpleNamespace(x=100.0, y=1.75 if x_direction > 0 else -1.75)
    forward = SimpleNamespace(x=float(x_direction), y=0.0)
    transform = SimpleNamespace(location=location, get_forward_vector=lambda: forward)
    return SimpleNamespace(transform=transform, lane_width=3.5)


class ExcursionTargets(unittest.TestCase):
    def test_both_directions_cross_toward_center(self):
        east, west = waypoint(1), waypoint(-1)
        self.assertEqual(target_xy(east, frame_index=0), [100.0, 1.75])
        self.assertEqual(target_xy(west, frame_index=0), [100.0, -1.75])
        self.assertLess(target_xy(east, frame_index=40)[1], 0)
        self.assertGreater(target_xy(west, frame_index=40)[1], 0)
        self.assertAlmostEqual(target_xy(east, frame_index=24)[1], 1.75 - 1.3125)

    def test_invalid_timing_width_and_fraction_rejected(self):
        route = waypoint(1)
        with self.assertRaisesRegex(ValueError, 'timing'):
            target_xy(route, frame_index=-1)
        route.lane_width = 0
        with self.assertRaisesRegex(ValueError, 'lane width'):
            target_xy(route, frame_index=40)
        route.lane_width = 3.5
        with self.assertRaisesRegex(ValueError, 'fraction'):
            target_xy(route, frame_index=40, requested_fraction=1.0)

    def test_original_reference_stays_on_selected_lane_after_crossing(self):
        start = SimpleNamespace(road_id=9, lane_id=-1)
        nearest = SimpleNamespace(road_id=9, lane_id=1, s=25.0)
        selected = SimpleNamespace(road_id=9, lane_id=-1, s=25.0)
        class Map:
            def get_waypoint(self, _location):
                return nearest
            def get_waypoint_xodr(self, road_id, lane_id, s):
                self.request = (road_id, lane_id, s)
                return selected
        road_map = Map()
        self.assertIs(pinned_subject_waypoint(road_map, object(), start), selected)
        self.assertEqual(road_map.request, (9, -1, 25.0))
        road_map.get_waypoint_xodr = lambda *_args: None
        with self.assertRaisesRegex(ValueError, 'travel lane reference'):
            pinned_subject_waypoint(road_map, object(), start)


if __name__ == '__main__':
    unittest.main()
