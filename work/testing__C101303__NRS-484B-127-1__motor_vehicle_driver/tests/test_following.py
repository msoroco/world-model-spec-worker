import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('following', ROOT / 'following.py')
following = importlib.util.module_from_spec(spec)
spec.loader.exec_module(following)
CASE = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver__following_base'


def box(x):
    return [[x-1, -1, 0], [x-1, 1, 0], [x+1, -1, 0], [x+1, 1, 0]]


def fixture(root):
    context = {'case_id': CASE, 'rate_hz': 20, 'duration_s': 24,
               'route_source': 'Native CARLA connected waypoints',
               'common_following_route_xy_m': [[0, 0], [100, 0]],
               'condition_source': 'original weather and road context',
               'road_id': 12, 'following_lane_id': -1, 'target_lane_id': -2,
               'hill_crest': {'source_ref': 'Native CARLA map waypoint elevation',
                              'crest_station_m': 11}}
    rows = []
    for i, t in enumerate([14, 17, 20, 21]):
        rows.append({'frame': 280+i, 'time_s': t,
                     'ego': {'actor_id': 1, 'source_ref': 'Native CARLA actor transform and bounding box',
                             'body_vertices_m': box(10+i), 'speed_mps': 9},
                     'leader': {'actor_id': 2, 'source_ref': 'Native CARLA actor transform and bounding box',
                                'body_vertices_m': box(30+i), 'speed_mps': 8},
                     'surrounding_vehicle_count': 1, 'traffic_source': 'Native CARLA actor inventory',
                     'highway_condition': {'source_ref': 'original weather and road context',
                                           'native_fog_density': 0, 'native_precipitation_strength': 0,
                                           'observed_tire_friction': 2.0},
                     'lane_change': {'source_ref': 'Native lane waypoint and route',
                                     'ego_road_id': 12, 'leader_road_id': 12,
                                     'ego_lane_id': -2 if t > 20 else -1,
                                     'leader_lane_id': -1,
                                     'started': t > 20}})
    (root / 'following-context.json').write_text(json.dumps(context))
    (root / 'following-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    acquisition = {name: {'kind': 'original_native', 'sha256': hashlib.sha256((root/name).read_bytes()).hexdigest()}
                   for name in ('following-context.json', 'following-history.jsonl')}
    (root / 'acquisition.json').write_text(json.dumps(acquisition))
    return rows


class FollowingTest(unittest.TestCase):
    def test_route_projection_and_gap(self):
        self.assertEqual(following.route_station([6, 2], [[0, 0], [10, 0]])['station_m'], 6)
        self.assertAlmostEqual(following.body_gap(box(10), box(30), [[0, 0], [100, 0]]), 18)
        with self.assertRaisesRegex(ValueError, 'outside common following route'):
            following.body_gap(box(10), [[20, 10, 0]]*4, [[0, 0], [100, 0]])

    def test_source_bound_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            result = following.measure(root, CASE, diagnostic=True)
            self.assertEqual(result['mean_along_route_body_gap_m'], 18)
            self.assertEqual(result['mean_relative_speed_mps'], 1)
            self.assertEqual(result['steady_frame_count'], 3)
            self.assertEqual(result['lane_change_first_frame'], 283)
            self.assertEqual(result['legal_reasonableness_verdict'], 'unresolved')
            with self.assertRaisesRegex(ValueError, 'does not cover capture duration'):
                following.measure(root, CASE)

    def test_missing_or_changed_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = fixture(root)
            rows[-1]['lane_change']['started'] = False
            rows[-1]['lane_change']['ego_lane_id'] = -1
            (root / 'following-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'stale original Native source'):
                following.measure(root, CASE, diagnostic=True)
            acquisition = json.loads((root / 'acquisition.json').read_text())
            acquisition['following-history.jsonl']['sha256'] = hashlib.sha256((root/'following-history.jsonl').read_bytes()).hexdigest()
            (root / 'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'transition missing'):
                following.measure(root, CASE, diagnostic=True)
            (root / 'following-context.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                following.measure(root, CASE, diagnostic=True)

    def test_rejects_crest_outside_realized_following_window(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            context = json.loads((root/'following-context.json').read_text())
            context['hill_crest']['crest_station_m'] = 70
            (root/'following-context.json').write_text(json.dumps(context))
            acquisition = json.loads((root/'acquisition.json').read_text())
            acquisition['following-context.json']['sha256'] = hashlib.sha256(
                (root/'following-context.json').read_bytes()).hexdigest()
            (root/'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'not traversed'):
                following.measure(root, CASE, diagnostic=True)


if __name__ == '__main__':
    unittest.main()
