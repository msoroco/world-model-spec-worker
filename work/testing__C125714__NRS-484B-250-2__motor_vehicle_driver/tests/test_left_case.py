import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def transform(x, y, yaw):
    return NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))


class Map:
    name = 'SyntheticFixtureTown'

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road:
            raise AssertionError('Native waypoint was projected')
        if location.x < -5:
            return NS(is_junction=False, road_id=11, lane_id=-1, lane_type='Driving')
        if abs(location.y) > 5:
            return NS(is_junction=False, road_id=22, lane_id=-1, lane_type='Driving')
        return NS(is_junction=True, road_id=33, lane_id=-1, lane_type='Driving',
                  get_junction=lambda: NS(id=7))


class LeftCaseTests(unittest.TestCase):
    def test_left_native_waypoints_and_right_rejected(self):
        construction = json.loads((ROOT / 'cases/source_verified_other_left_near_time/construction.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        namespace = {'__name__': 'left_native_pair'}
        exec(compile(files['native_pair.py'], 'left_native_pair.py', 'exec'), namespace)
        site = config['site']
        poses = {key: transform(*site[key][0:2], site[key][3]) for key in
                 ('ego_approach', 'ego_entry', 'other_approach', 'other_entry')}
        plan = namespace['plan_pair'](Map(), site, poses)
        self.assertLess(plan['other_lateral_to_ego_right_m'], 0)
        self.assertGreater(plan['ego_lateral_to_other_right_m'], 0)
        self.assertEqual(plan['native_junction_id'], 7)
        wrong = dict(poses, other_approach=transform(0, -10, 90),
                     other_entry=transform(0, -4, 90))
        with self.assertRaisesRegex(ValueError, 'not on ego left'):
            namespace['plan_pair'](Map(), site, wrong)


if __name__ == '__main__':
    unittest.main()
