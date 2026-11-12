import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/source_verified_opposite_straight'
sys.path.insert(0, str(ROOT))


def transform(x, y, yaw):
    return NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))


class Map:
    name = 'SyntheticFixtureTown'

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road:
            raise AssertionError('Native waypoint projected')
        if location.x < -5:
            return NS(is_junction=False, road_id=11, lane_id=-1, lane_type='Driving')
        if location.x > 5:
            return NS(is_junction=False, road_id=22, lane_id=-1, lane_type='Driving')
        return NS(is_junction=True, road_id=33, lane_id=-1, lane_type='Driving',
                  get_junction=lambda: NS(id=7))


class OppositeStraightCaseTests(unittest.TestCase):
    def test_opposite_native_pair_and_original_headings(self):
        construction = json.loads((CASE / 'construction.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        pair = {'__name__': 'opposite_native_pair'}
        exec(compile(files['native_pair.py'], 'native_pair.py', 'exec'), pair)
        poses = {key: transform(*config['site'][key][:2], config['site'][key][3])
                 for key in ('ego_approach', 'ego_entry', 'other_approach', 'other_entry')}
        plan = pair['plan_pair'](Map(), config['site'], poses)
        self.assertEqual(plan['native_junction_id'], 7)
        self.assertEqual({plan['approaches'][role]['road_id'] for role in ('ego', 'other')}, {11, 22})
        with self.assertRaisesRegex(ValueError, 'heading does not approach crossing entry'):
            pair['plan_pair'](Map(), config['site'], dict(poses,
                other_approach=transform(10, 3.5, 90)))

        diagnostic = json.loads((CASE / 'diagnostic.json').read_text())
        analyzer = {'__name__': 'opposite_entry_measurements'}
        exec(compile(files['entry_measurements.py'], 'entry_measurements.py', 'exec'), analyzer)
        with tempfile.TemporaryDirectory() as temporary:
            for name in ('road_geometry.json', 'crossing_history.jsonl', 'video_frames.jsonl'):
                (Path(temporary) / name).write_text(diagnostic['files'][name])
            measured = analyzer['analyze'](Path(temporary))
            self.assertTrue(measured['opposite_directions'])
            self.assertEqual(measured['geometric_yield_candidate'], 'not_applicable_opposite_straight')
            self.assertEqual(abs(measured['approach_heading_difference_deg']), 180)
            geometry = json.loads(diagnostic['files']['road_geometry.json'])
            geometry['other_approach_heading_deg'] = 90
            (Path(temporary) / 'road_geometry.json').write_text(json.dumps(geometry))
            with self.assertRaisesRegex(ValueError, 'Opposite sourced approach'):
                analyzer['analyze'](Path(temporary))


if __name__ == '__main__':
    unittest.main()
