import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('construction', ROOT / 'construction.py')
construction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(construction)


def samples():
    heights = [0, .3, .7, 1.2, 1.8, 1.5, 1.1, .6, .2]
    return [{'road_id': 12, 'lane_id': -1, 'lane_type': 'Driving',
             'station_m': i*4, 'z_m': h,
             'adjacent_lane': {'road_id': 12, 'lane_id': -2,
                               'lane_type': 'Driving', 'forward_dot': .99}}
            for i, h in enumerate(heights)]


class ConstructionTest(unittest.TestCase):
    def test_connected_crest_and_forward_adjacent_lane(self):
        result = construction.validate_hill_route(samples())
        self.assertEqual(result['crest_station_m'], 16)
        self.assertEqual(result['target_lane_id'], -2)

    def test_rejects_flat_or_opposing_or_disconnected_route(self):
        cases = [(lambda x: [p.update(z_m=0) for p in x], 'no measured hill crest'),
                 (lambda x: x[-2]['adjacent_lane'].update(forward_dot=-1), 'not a forward'),
                 (lambda x: x[4].update(station_m=100), 'disconnected')]
        for mutate, error in cases:
            route = samples()
            mutate(route)
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                construction.validate_hill_route(route)

    def test_control_and_following_window(self):
        near = construction.speed_command(9, 10, 8, 20, 2)
        far = construction.speed_command(9, 10, 40, 20, 0)
        self.assertGreater(near['brake'], 0)
        self.assertGreater(far['throttle'], 0)
        self.assertEqual(construction.lane_change_phase(17, 21, -1, -1), 'following')
        self.assertEqual(construction.lane_change_phase(22, 21, -1, -2), 'changed')
        with self.assertRaisesRegex(ValueError, 'during following'):
            construction.lane_change_phase(17, 21, -1, -2)


if __name__ == '__main__':
    unittest.main()
