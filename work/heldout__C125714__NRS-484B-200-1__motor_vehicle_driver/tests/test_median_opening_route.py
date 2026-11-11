from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from median_opening_route import select_median_opening_route
from median_opening_preflight import check
from test_right_half_route import mapped_route


def reference(direction=1):
    return {'source': 'authored-map-reference', 'map_name': 'CPU-test-map',
            'road_id': 7, 'lane_id': -direction,
            'opening_polygon_xy': [[4, -1], [16, -1], [16, 1], [4, 1]]}


class MedianOpeningRouteTests(unittest.TestCase):
    def test_preflight_binds_exact_case_and_direction_without_carla(self):
        east_case = ('heldout__C125714__NRS-484B-200-1__motor_vehicle_driver'
                     '__baseline_right_east')
        self.assertEqual(check({**reference(), 'travel_direction': 'east'},
                               east_case), 'east')
        with self.assertRaisesRegex(ValueError, 'direction differs'):
            check({**reference(), 'travel_direction': 'west'}, east_case)
        with self.assertRaisesRegex(ValueError, 'case identity differs'):
            check({**reference(), 'travel_direction': 'east'}, 'other')

    def test_east_route_intersects_sourced_opening_at_multiple_points(self):
        world_map, points = mapped_route()
        world_map.name = 'CPU-test-map'
        route, samples = select_median_opening_route(world_map, reference())
        self.assertEqual(route, points[:13])
        self.assertEqual(samples, [2, 3, 4, 5, 6])

    def test_west_route_uses_opposite_directed_lane(self):
        world_map, points = mapped_route(direction=-1)
        world_map.name = 'CPU-test-map'
        west = {**reference(direction=-1),
                'opening_polygon_xy': [[-16, -1], [-4, -1],
                                       [-4, 1], [-16, 1]]}
        route, samples = select_median_opening_route(
            world_map, west, direction='west')
        self.assertEqual(route, points[:13])
        self.assertEqual(samples, [2, 3, 4, 5, 6])

    def test_wrong_map_lane_and_unrelated_polygon_rejected(self):
        world_map, _ = mapped_route()
        world_map.name = 'CPU-test-map'
        for change, message in [({'map_name': 'another-map'}, 'source map differs'),
                                ({'lane_id': 1}, 'No directed route'),
                                ({'opening_polygon_xy': [[40, -1], [50, -1],
                                                         [50, 1], [40, 1]]},
                                 'No directed route')]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                select_median_opening_route(world_map, {**reference(), **change})

    def test_disconnected_opposing_lane_and_invalid_reference_rejected(self):
        world_map, _ = mapped_route(opposite_gap=True)
        world_map.name = 'CPU-test-map'
        with self.assertRaisesRegex(ValueError, 'No directed route'):
            select_median_opening_route(world_map, reference())
        world_map, _ = mapped_route()
        world_map.name = 'CPU-test-map'
        with self.assertRaisesRegex(ValueError, 'zero area'):
            select_median_opening_route(world_map, {**reference(),
                'opening_polygon_xy': [[0, 0], [1, 0], [2, 0]]})
        with self.assertRaisesRegex(ValueError, 'map source required'):
            select_median_opening_route(world_map, {**reference(), 'source': ''})


if __name__ == '__main__':
    unittest.main()
