import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_crest_audit import ASSIGNMENT, audit


def write(root, name, data):
    path = root / name
    path.write_text(data, encoding='utf-8')
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(root):
    grades = [{'s_m': s, 'z_m': z, 'source_ref': 'native-map'} for s, z in
              ((0, 0), (100, 1), (200, 3), (250, 4), (300, 3), (400, 0))]
    grade_source = write(root, 'grade.json', json.dumps(grades))
    prescribed_limit_source = write(root, 'reviewed-limit.json', json.dumps({
        'road_id': 603, 'source_kind': 'reviewed_original_limit',
        'prescribed_limit_mps': 15.0}))
    context = {'map_grade_sha256': grade_source['sha256'], 'road_id': 603,
               'highway_status': 'source_observed_road',
               'highway_source_ref': 'original-native-map',
               'prescribed_limit_mps': 15.0,
               'limit_source_ref': 'reviewed-limit.json:' + prescribed_limit_source['sha256'],
               'ego_actor_id': 'ego-1', 'other_actor_id': 'other-2',
               'lawful_entry_review': 'unresolved', 'due_care_review': 'unresolved'}
    other_route = [{'road_id': 603, 'lane_id': 1, 's_m': s,
                    'source_ref': 'original-native-opposing-waypoint'}
                   for s in (400, 350, 300, 250, 200)]
    frames = []
    identities = []
    for i in range(900):
        time = i / 20
        frames.append({'frame_id': i+100, 'time_s': time, 'ego_s_m': i*.5,
                       'ego_speed_mps': 10 if i < 300 else 8,
                       'other_s_m': 400-i*.2, 'body_clearance_m': 10,
                       'ego_actor_id': 'ego-1', 'other_actor_id': 'other-2',
                       'other_source_ref': 'original-other-actor-transform',
                       'source_ref': 'original-motion'})
        identities.append({'video_frame': i, 'carla_frame': i+100, 'time_s': time})
    manifest = {'case_id': ASSIGNMENT+'__early_decrease', 'profile': 'early_decrease',
                'acquisition_kind': 'original_native', 'duration_s': 45,
                'rate_hz': 20, 'approach_start_m': 100,
                'grade_source': grade_source,
                'prescribed_limit_source': prescribed_limit_source,
                'context_source': write(root, 'context.json', json.dumps(context)),
                'other_route_source': write(root, 'other-route.json', json.dumps(other_route)),
                'motion_source': write(root, 'motion.json', json.dumps(frames)),
                'frame_map_source': write(root, 'frames.jsonl', '\n'.join(map(json.dumps, identities))+'\n'),
                'camera_sources': {name: write(root, name+'.txt', 'camera-'+name)
                                   for name in ('front', 'left', 'right', 'rear')}}
    return manifest


class SavedCrestAuditTests(unittest.TestCase):
    def test_exact_source_bound_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = audit(root, fixture(root))
            self.assertEqual(result['frame_count'], 900)
            self.assertTrue(result['checks']['time_join'])
            self.assertFalse(result['checks']['actual_pixels'])
            self.assertEqual(result['physical_measurements']['crest_station_m'], 250)
            self.assertGreater(result['crest_crossing']['crossing_station_m'], 249)
            self.assertEqual(result['source_context']['lawful_entry_review'], 'unresolved')
            self.assertTrue(result['source_context']['below_limit_at_first_approach'])

    def test_rejects_saved_motion_that_never_crosses_crest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            motion = json.loads((root/'motion.json').read_text())
            for frame in motion:
                frame['ego_s_m'] = min(frame['ego_s_m'], 249.5)
            manifest['motion_source'] = write(root, 'motion.json', json.dumps(motion))
            with self.assertRaisesRegex(ValueError, 'crest crossing'):
                audit(root, manifest)

    def test_rejects_source_or_case_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            manifest['case_id'] = ASSIGNMENT+'__wrong'
            with self.assertRaisesRegex(ValueError, 'identity'):
                audit(root, manifest)
            manifest['case_id'] = ASSIGNMENT+'__early_decrease'
            (root/'front.txt').write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                audit(root, manifest)

    def test_rejects_missing_camera_and_frame_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            del manifest['camera_sources']['rear']
            with self.assertRaisesRegex(ValueError, 'camera'):
                audit(root, manifest)
            manifest = fixture(root)
            motion = json.loads((root/'motion.json').read_text())
            motion[15]['frame_id'] = 999
            manifest['motion_source'] = write(root, 'motion.json', json.dumps(motion))
            with self.assertRaisesRegex(ValueError, 'join'):
                audit(root, manifest)

    def test_rejects_missing_limit_and_other_participant_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            context = json.loads((root/'context.json').read_text())
            del context['limit_source_ref']
            manifest['context_source'] = write(root, 'context.json', json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'prescribed limit source'):
                audit(root, manifest)
            manifest = fixture(root)
            route = json.loads((root/'other-route.json').read_text())
            route[2]['lane_id'] = -1
            manifest['other_route_source'] = write(root, 'other-route.json', json.dumps(route))
            with self.assertRaisesRegex(ValueError, 'opposing vehicle route'):
                audit(root, manifest)
            manifest = fixture(root)
            motion = json.loads((root/'motion.json').read_text())
            motion[150]['other_actor_id'] = 'ego-1'
            manifest['motion_source'] = write(root, 'motion.json', json.dumps(motion))
            with self.assertRaisesRegex(ValueError, 'participant source join'):
                audit(root, manifest)

    def test_rejects_original_precrest_speed_at_prescribed_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            context = json.loads((root/'context.json').read_text())
            context['prescribed_limit_mps'] = 10.0
            limit = json.loads((root/'reviewed-limit.json').read_text())
            limit['prescribed_limit_mps'] = 10.0
            manifest['prescribed_limit_source'] = write(root, 'reviewed-limit.json', json.dumps(limit))
            context['limit_source_ref'] = ('reviewed-limit.json:' +
                                           manifest['prescribed_limit_source']['sha256'])
            manifest['context_source'] = write(root, 'context.json', json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'below-limit precrest'):
                audit(root, manifest)

    def test_rejects_changed_or_decoy_reviewed_limit_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            (root / 'reviewed-limit.json').write_text('changed\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                audit(root, manifest)
            manifest = fixture(root)
            decoy = json.loads((root / 'reviewed-limit.json').read_text())
            decoy['road_id'] = 604
            manifest['prescribed_limit_source'] = write(root, 'reviewed-limit.json', json.dumps(decoy))
            context = json.loads((root / 'context.json').read_text())
            context['limit_source_ref'] = ('reviewed-limit.json:' +
                                           manifest['prescribed_limit_source']['sha256'])
            manifest['context_source'] = write(root, 'context.json', json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'prescribed limit source'):
                audit(root, manifest)


if __name__ == '__main__':
    unittest.main()
