import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

p = Path(__file__).resolve().parents[1] / 'saved_audit.py'
spec = importlib.util.spec_from_file_location('saved_audit_c147331', p)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_sealed_original_history_and_missing_source(self):
        fixed = dict(case='case-x', ego_id='ego', map_sha256='map',
                     lane_marking_source_sha256='marking',
                     legal_controlled_access_source_sha256='designation',
                     public_highway_boundary_source_sha256='boundary',
                     camera_plan_sha256='camera', vehicle_class='ordinary',
                     approach='north', route_class='outside_nonshoulder',
                     sign_source_sha256='sign', emergency_record_source_sha256='emergency',
                     subsection3_authorization_source_sha256='authorization',
                     source_sha256='frame', capture_packet_sha256='packet',
                     sign_permits_shoulder=False, emergency_required=False,
                     subsection3_authorized=False)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'original.jsonl'
            rows = [dict(fixed, original_frame=100+i) for i in range(900)]
            def write():
                path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
                return sha256(path.read_bytes()).hexdigest()
            digest = write()
            self.assertEqual(m.audit_history(path, digest, 'case-x', 'map')['frame_count'], 900)
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                m.audit_history(path, '0'*64, 'case-x', 'map')
            rows[499]['capture_packet_sha256'] = ''
            digest = write()
            with self.assertRaisesRegex(ValueError, 'capture packet source missing'):
                m.audit_history(path, digest, 'case-x', 'map')
            rows[499]['capture_packet_sha256'] = 'packet'
            rows[499]['original_frame'] = 999
            digest = write()
            with self.assertRaisesRegex(ValueError, 'original-frame join mismatch'):
                m.audit_history(path, digest, 'case-x', 'map')

if __name__ == '__main__':
    unittest.main()
