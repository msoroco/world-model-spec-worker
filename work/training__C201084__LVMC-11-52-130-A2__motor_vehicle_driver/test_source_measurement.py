"""Synthetic CPU source-join checks, never original Native observations."""
import json
import tempfile
import unittest
from pathlib import Path

from fire_lane_survey import build
from source_measurement import analyze

HERE = Path(__file__).resolve().parent


def make_attempt(directory, case, *, corrupt=None):
    survey = json.loads((HERE/'draft-fire-lane-survey.json').read_text())
    def probe(xy):
        return {'map_name': survey['map_name'], 'road_id': 17, 'lane_id': -1,
                'drivable_access': True, 'source_kind': 'synthetic_construction_probe'}
    plan = build(survey, probe)
    plan['sign_readback'] = {'actor_id': 101, 'type_id': 'static.prop.fire_lane_sign',
                             'position_xy_m': [6, -1],
                             'source_kind': 'synthetic_native_sample'}
    if corrupt == 'sign':
        plan['sign_readback']['actor_id'] = 999
    (directory/'native-survey-readback.json').write_text(json.dumps(plan)+'\n')
    x = 10 if case == 'reference' else 24
    body = [[x-0.5, 0.7, 0], [x+0.5, 0.7, 0],
            [x+0.5, 1.3, 0], [x-0.5, 1.3, 0]]
    actors = []
    frames = []
    for i, speed in enumerate((4, 2, 0, 0)):
        actors.append({'frame': 100+i, 'source_kind': 'synthetic_native_sample',
                       'ego_actor_id': 41, 'driving_road_id': 17,
                       'following_actor_id': 42, 'following_road_id': 17,
                       'following_velocity_xyz_mps': [3, 0, 0],
                       'following_body_vertices_xyz_m': [
                           [x-12.5, 0.7, 0], [x-11.5, 0.7, 0],
                           [x-11.5, 1.3, 0], [x-12.5, 1.3, 0]],
                       'following_gap_m': 12,
                       'sign_actor_id': 101,
                       'ego_velocity_xyz_mps': [speed, 0, 0],
                       'ego_body_vertices_xyz_m': body})
        frames.append({'video_frame': i, 'carla_frame': 100+i,
                       'time_s': i/20})
    if corrupt == 'frame':
        frames[2]['carla_frame'] = 202
    if corrupt == 'body':
        actors[2]['ego_body_vertices_xyz_m'] = [[x, 1, 0]]
    for name, values in [('native-actors.jsonl', actors),
                         ('video_frames.jsonl', frames)]:
        (directory/name).write_text(''.join(json.dumps(row)+'\n' for row in values))


class SourceMeasurementTests(unittest.TestCase):
    def test_inside_and_outside_from_retained_body(self):
        for case, inside in [('reference', True), ('contrast', False)]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                make_attempt(path, case)
                result = analyze(path, case, diagnostic=True)
                self.assertEqual(result['frames'], 4)
                self.assertEqual(result['near_zero_with_zone_overlap_frames'],
                                 2 if inside else 0)
                self.assertEqual(result['near_zero_disjoint_frames'],
                                 0 if inside else 2)
                self.assertFalse(result['fire_code_designation_verified'])
                self.assertFalse(result['physical_or_legal_completion_claimed'])

    def test_wrong_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            make_attempt(path, 'reference', corrupt='frame')
            with self.assertRaisesRegex(ValueError, 'frame join differs'):
                analyze(path, 'reference', diagnostic=True)

    def test_wrong_sign_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            make_attempt(path, 'reference', corrupt='sign')
            with self.assertRaisesRegex(ValueError, 'Sign actor readback provenance'):
                analyze(path, 'reference', diagnostic=True)

    def test_missing_body_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            make_attempt(path, 'reference', corrupt='body')
            with self.assertRaisesRegex(ValueError, 'body source incomplete'):
                analyze(path, 'reference', diagnostic=True)

    def test_following_source_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            make_attempt(path, 'reference')
            rows = [json.loads(line) for line in
                    (path/'native-actors.jsonl').read_text().splitlines()]
            rows[2].pop('following_velocity_xyz_mps')
            (path/'native-actors.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'body source incomplete'):
                analyze(path, 'reference', diagnostic=True)

    def test_short_fixture_cannot_prove_real_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            make_attempt(path, 'reference')
            plan = json.loads((path/'native-survey-readback.json').read_text())
            plan['cases']['reference']['road_readback']['source_kind'] = 'original_carla_map_readback'
            plan['sign_readback']['source_kind'] = 'original_carla_actor_readback'
            (path/'native-survey-readback.json').write_text(json.dumps(plan)+'\n')
            with self.assertRaisesRegex(ValueError, 'shorter than thirty seconds'):
                analyze(path, 'reference')


if __name__ == '__main__':
    unittest.main()
