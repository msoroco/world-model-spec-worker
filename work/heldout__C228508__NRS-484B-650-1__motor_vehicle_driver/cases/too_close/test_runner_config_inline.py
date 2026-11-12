import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import _select_route, check_config


class Waypoint:
    def __init__(self, x, road):
        self.road_id = road
        self.lane_id = 1
        self.is_junction = False
        self.transform = NS(location=NS(x=x, y=0, z=0))

    def next(self, step):
        return [Waypoint(self.transform.location.x + step, self.road_id)]


class Map:
    def get_spawn_points(self):
        return [NS(location=NS(x=0, y=0, z=0)),
                NS(location=NS(x=100, y=0, z=0))]

    def get_waypoint(self, location):
        return Waypoint(location.x, int(location.x / 100) + 1)


class RunnerChecks(unittest.TestCase):
    def test_risk_knobs_and_route_selection(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        self.assertEqual(check_config(config), config['selected_case_id'])
        config['selected_case_id'] = config['selected_case_id'].rsplit('__', 1)[0] + '__repeated_following'
        config['case']['case_id'] = config['selected_case_id']
        config['closing_encounters'] = 2
        config['engineering'] = {}
        self.assertEqual(check_config(config), config['selected_case_id'])
        one = json.loads(json.dumps(config))
        one['selected_case_id'] = one['selected_case_id'].replace('repeated_following', 'one_secondary_act')
        one['case']['case_id'] = one['selected_case_id']
        one['closing_encounters'] = 1
        self.assertEqual(check_config(one), one['selected_case_id'])
        one['closing_encounters'] = 2
        with self.assertRaisesRegex(ValueError, 'secondary-act count'):
            check_config(one)
        slow = json.loads(json.dumps(config))
        slow['selected_case_id'] = slow['selected_case_id'].replace('repeated_following', 'no_speed')
        slow['case']['case_id'] = slow['selected_case_id']
        slow['engineering'] = {'requested_speed_cap_mps': 13}
        self.assertEqual(check_config(slow), slow['selected_case_id'])
        slow['engineering'] = {}
        with self.assertRaisesRegex(ValueError, 'ego speed request'):
            check_config(slow)
        for knob, value in [('route_candidate_index', 1),
                            ('lead_spawn_station_m', 35),
                            ('closing_lead_speed_mps', 9)]:
            variant = dict(config)
            variant['engineering'] = {knob: value}
            self.assertEqual(check_config(variant), config['selected_case_id'])
        route0, _ = _select_route(Map(), candidate_index=0)
        route1, _ = _select_route(Map(), candidate_index=1)
        self.assertEqual(route0[0].road_id, 1)
        self.assertEqual(route1[0].road_id, 2)
        with self.assertRaisesRegex(ValueError, 'requested 2.2 km'):
            _select_route(Map(), candidate_index=2)
        variant['engineering'] = {'route_candidate_index': 3}
        with self.assertRaisesRegex(ValueError, 'Unsupported route'):
            check_config(variant)


if __name__ == '__main__':
    unittest.main()
