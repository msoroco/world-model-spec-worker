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
    frames = []
    identities = []
    for i in range(900):
        time = i / 20
        frames.append({'frame_id': i+100, 'time_s': time, 'ego_s_m': i*.5,
                       'ego_speed_mps': 10 if i < 300 else 8,
                       'other_s_m': 400-i*.2, 'body_clearance_m': 10,
                       'source_ref': 'original-motion'})
        identities.append({'video_frame': i, 'carla_frame': i+100, 'time_s': time})
    manifest = {'case_id': ASSIGNMENT+'__early_decrease', 'profile': 'early_decrease',
                'acquisition_kind': 'original_native', 'duration_s': 45,
                'rate_hz': 20, 'approach_start_m': 100,
                'grade_source': write(root, 'grade.json', json.dumps(grades)),
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


if __name__ == '__main__':
    unittest.main()
