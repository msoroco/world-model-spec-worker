import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'saved_audit.py'
spec = importlib.util.spec_from_file_location('saved_c150153', MODULE)
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)


class SavedAuditTests(unittest.TestCase):
    def test_sealed_900_frame_history_and_rejections(self):
        fixed = {k: k + '-hash' for k in ('ego_id', 'fixture_id', 'fixture_identity_sha256',
                 'fixture_geometry_sha256', 'fixture_blueprint_sha256', 'map_sha256',
                 'site_sha256', 'camera_plan_sha256', 'municipal_jurisdiction_sha256',
                 'sidewalk_sha256', 'curb_sha256', 'frame_map_sha256')}
        rows = [dict(fixed, case_id='front_park', original_frame=i,
                     time_s=i / 20, source_sha256='source',
                     body_footprint_source_sha256='body', body_west_x_m=10.0,
                     body_east_x_m=12.0, fixture_physically_present=True,
                     body_curb_gap_m=0.3, ego_speed_mps=0.0,
                     activity_observation='parked', exception_kind='none') for i in range(900)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'native.jsonl'
            def seal():
                path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
                return hashlib.sha256(path.read_bytes()).hexdigest()
            digest = seal()
            result = a.audit_original_history(path, digest, 'front_park', 'site_sha256-hash')
            self.assertEqual(result['frame_count'], 900)
            self.assertIsNone(result['legal_judgment'])
            rows[400]['fixture_geometry_sha256'] = 'changed'
            digest = seal()
            with self.assertRaisesRegex(ValueError, 'fixed source changed'):
                a.audit_original_history(path, digest, 'front_park', 'site_sha256-hash')
            rows[400]['fixture_geometry_sha256'] = fixed['fixture_geometry_sha256']
            rows[500]['original_frame'] = 600
            digest = seal()
            with self.assertRaisesRegex(ValueError, 'frame or case join'):
                a.audit_original_history(path, digest, 'front_park', 'site_sha256-hash')
            rows[500]['original_frame'] = 500
            digest = seal()
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                a.audit_original_history(path, '0' * 64, 'front_park', 'site_sha256-hash')
            self.assertEqual(a.audit_original_history(path, digest, 'front_park', 'site_sha256-hash')['frame_count'], 900)


if __name__ == '__main__':
    unittest.main()
