import unittest
from types import SimpleNamespace as NS

from native_runner import _native_map_readback, check
from officer_direction import Crossing


class NativeRunnerCheckTest(unittest.TestCase):
    def test_exact_cases_and_both_directions_check_without_carla(self):
        for suffix in ('reference', 'contrast'):
            for direction in (-1, 1):
                result = check(suffix, direction)
                self.assertTrue(result['case_id'].endswith('__' + suffix))
                self.assertEqual(600, result['frames'])
                self.assertFalse(result['physical_success_claimed'])
        with self.assertRaisesRegex(ValueError, 'Exact comparison'):
            check('third_case', 1)

    def test_native_lane_readback_rejects_wrong_direction(self):
        class Map:
            def __init__(self, wrong=False):
                self.wrong = wrong
                self.calls = []

            def get_waypoint(self, location, **kwargs):
                self.calls.append((location.x, location.y, kwargs))
                direction = 1 if location.y < 0 else -1
                return NS(road_id=177225, lane_id=-direction,
                          lane_width=3.5,
                          transform=NS(get_forward_vector=lambda: NS(
                              x=-direction if self.wrong else direction,
                              y=0, z=0)))

            def to_opendrive(self):
                return '<OpenDRIVE/>'

        carla = NS(Location=lambda **kwargs: NS(**kwargs),
                   LaneType=NS(Driving='driving'))
        for direction in (-1, 1):
            mapping = Map()
            result = _native_map_readback(carla, NS(get_map=lambda: mapping),
                                          Crossing(), direction)
            self.assertEqual(3, len(result['lane_readback']))
            self.assertFalse(result['physical_rail_placement_verified'])
            self.assertEqual({-1.75 * direction},
                             {entry[1] for entry in mapping.calls})
            with self.assertRaisesRegex(ValueError, 'direction or width'):
                _native_map_readback(carla, NS(get_map=lambda: Map(wrong=True)),
                                     Crossing(), direction)


if __name__ == '__main__':
    unittest.main()
