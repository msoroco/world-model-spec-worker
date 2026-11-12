"""Exercise the opposite-direction candidate's Native map and authored turn."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/off_opposite_left_turn'
spec = importlib.util.spec_from_file_location('opposite_pair', CASE / 'native_pair.py')
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)
sys.path.insert(0, str(CASE))
from opposite_turn_measurement import measure_opposite_turn_context


def pose(values):
    return NS(location=NS(x=values[0], y=values[1]), rotation=NS(yaw=values[3]))


class OppositeMap:
    name = 'TownX'

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road is not False:
            raise AssertionError('Native waypoint projection is forbidden')
        inside = 10 <= location.x <= 20 and -5 <= location.y <= 5
        lane = -1 if location.y < 0 else 1
        return NS(road_id=1, lane_id=lane, lane_type='Driving',
                  is_junction=inside, get_junction=lambda: NS(id=44))


class OppositeCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((CASE / 'config.json').read_text())
        cls.site = cls.config['site']

    def transforms(self):
        return {key: pose(self.site[key]) for key in
                ('ego_approach', 'ego_entry', 'other_approach', 'other_entry')}

    def test_same_road_opposed_lanes_and_real_turn_route(self):
        plan = pair.plan_pair(OppositeMap(), self.site, self.transforms(), 'opposite')
        self.assertEqual(plan['approaches']['ego']['road_id'],
                         plan['approaches']['other']['road_id'])
        self.assertNotEqual(plan['approaches']['ego']['lane_id'],
                            plan['approaches']['other']['lane_id'])
        self.assertEqual(plan['ego_highway_id'], plan['other_highway_id'])
        from route_control import validate_pair_routes, steering_command
        validate_pair_routes(plan, self.site['routes'])
        route = self.site['routes']['other']
        steer, progress = steering_command(17, 1.75, 180, route, progress=2)
        self.assertLess(steer, 0, 'Westbound to southbound must command a left turn')
        self.assertGreaterEqual(progress, 2)

    def test_reject_wrong_highway_or_heading(self):
        site = dict(self.site, other_highway_id='north-south')
        with self.assertRaisesRegex(ValueError, 'one sourced highway'):
            pair.plan_pair(OppositeMap(), site, self.transforms(), 'opposite')
        transforms = self.transforms()
        transforms['other_approach'] = pose([30, 1.75, 0, 0])
        with self.assertRaisesRegex(ValueError, 'heading does not approach'):
            pair.plan_pair(OppositeMap(), self.site, transforms, 'opposite')

    def test_turn_measurement_requires_joined_original_motion(self):
        context = {'opposite_approach_with_left_turn': True,
                   'ego_highway_id': 'east-west', 'other_highway_id': 'east-west',
                   'ego_road_id': 1, 'other_road_id': 1,
                   'other_left_turn_route_xy_m': self.site['routes']['other']}
        poses = [(30, 1.75, 180, 0), (15, 1.75, 225, -0.3),
                 (15, -12, 270, -0.2)]
        rows = [{'frame': i, 'time_s': i / 20,
                 'other': {'position_xy_m': [x, y], 'heading_deg': yaw}}
                for i, (x, y, yaw, steer) in enumerate(poses)]
        controls = [{'frame': i, 'time_s': i / 20, 'other_steer': steer}
                    for i, (x, y, yaw, steer) in enumerate(poses)]
        measured = measure_opposite_turn_context(context, rows, controls)
        self.assertEqual(measured['observed_heading_deg'], [180, 270])
        self.assertEqual(measured['exception_judgment'], 'unresolved')
        controls[1]['frame'] = 20
        with self.assertRaisesRegex(ValueError, 'frame join'):
            measure_opposite_turn_context(context, rows, controls)
        controls[1]['frame'] = 1
        rows[-1]['other']['heading_deg'] = 180
        with self.assertRaisesRegex(ValueError, 'do not show'):
            measure_opposite_turn_context(context, rows, controls)


if __name__ == '__main__':
    unittest.main()
