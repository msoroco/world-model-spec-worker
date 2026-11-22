"""Small construction test shipped inside each exact offline bundle."""
import unittest

from construction import speed_command, validate_hill_route
from runner import load_scene


class OfflineCase(unittest.TestCase):
    def test_exact_scene_and_connected_crest(self):
        scene = load_scene()
        self.assertEqual(scene['layout'], 'hill_crest')
        self.assertEqual(scene['maneuver'], 'change_lane')
        heights = [0,.3,.7,1.2,1.8,1.5,1.1,.6,.2]
        route = [{'road_id': 12, 'lane_id': -1, 'lane_type': 'Driving',
                  'station_m': i*4, 'z_m': h,
                  'adjacent_lane': {'road_id': 12, 'lane_id': -2,
                                    'lane_type': 'Driving', 'forward_dot': .99}}
                 for i,h in enumerate(heights)]
        self.assertEqual(validate_hill_route(route)['target_lane_id'], -2)
        self.assertGreater(speed_command(6, scene['ego_target_speed_mps'],
                                         scene['target_body_gap_m']+10,
                                         scene['target_body_gap_m'], 0)['throttle'], 0)
        route[-2]['adjacent_lane']['forward_dot'] = -1
        with self.assertRaisesRegex(ValueError, 'not a forward'):
            validate_hill_route(route)


if __name__ == '__main__':
    unittest.main()
