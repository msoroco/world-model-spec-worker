import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

path = Path(__file__).resolve().parents[1] / 'saved_audit.py'
spec = importlib.util.spec_from_file_location('saved_audit', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def rows():
    fixed = {key: 'x' for key in ('ego_id','crossing_vehicle_id','occupant_id',
            'property_id','ego_blueprint','crossing_blueprint','property_blueprint',
            'map_sha256','camera_plan_sha256')}
    fixed.update(site_sha256='site', public_access_basis='highway')
    return [dict(fixed, original_frame=i, case_id='case-a',
                 occupant_vehicle_id='x', source_sha256='original',
                 control_command_source_sha256='control') for i in range(900)]


def write(path, samples):
    data = ''.join(json.dumps(x)+'\n' for x in samples).encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


class SavedAuditTests(unittest.TestCase):
    def test_full_original_history_and_hash(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'history.jsonl'
            sha = write(path, rows())
            result = module.audit_history(path, sha, 'case-a', 'site')
            self.assertEqual(result['frame_count'], 900)
            self.assertFalse(result['physical_visibility_verified'])
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                module.audit_history(path, '0'*64, 'case-a', 'site')
    def test_rejects_missing_frame_and_occupancy(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'history.jsonl'
            samples = rows(); samples.pop(10)
            with self.assertRaisesRegex(ValueError, 'frame count mismatch'):
                module.audit_history(path, write(path, samples), 'case-a', 'site')
            samples = rows(); samples[4]['occupant_vehicle_id'] = 'other'
            with self.assertRaisesRegex(ValueError, 'occupancy join mismatch'):
                module.audit_history(path, write(path, samples), 'case-a', 'site')
            samples = rows(); samples[4]['control_command_source_sha256'] = ''
            with self.assertRaisesRegex(ValueError, 'control source missing'):
                module.audit_history(path, write(path, samples), 'case-a', 'site')
    def test_comparison_positive_and_negative(self):
        fixed = {key: 'x' for key in ('map_sha256','site_sha256','public_access_basis',
                 'ego_blueprint','crossing_blueprint','property_blueprint','camera_plan_sha256')}
        a = dict(fixed, case_id='a', frame_count=900, original_history_sha256='h1', release_s=1)
        b = dict(fixed, case_id='b', frame_count=900, original_history_sha256='h2', release_s=4)
        self.assertEqual(module.audit_comparison(a,b,'release_s')['difference'], 'release_s')
        with self.assertRaisesRegex(ValueError, 'fixed source changed'):
            module.audit_comparison(a,dict(b,map_sha256='other'),'release_s')
        with self.assertRaisesRegex(ValueError, 'deliberate difference missing'):
            module.audit_comparison(a,dict(b,release_s=1),'release_s')

if __name__ == '__main__':
    unittest.main()
