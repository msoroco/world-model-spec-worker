import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit_pair


class ComparisonAuditTests(unittest.TestCase):
    def source(self, root, suffix, attended, map_hash='map-source'):
        case_id = ROOT.name + '__' + suffix
        fixed = {key: key + '-source' for key in (
            'ego_id', 'sign_id', 'site_sha256', 'jurisdiction_sha256',
            'fire_code_designation_sha256', 'posting_authority_sha256',
            'posted_extent_sha256', 'sign_identity_sha256',
            'sign_appearance_sha256', 'property_source_sha256',
            'curb_geometry_sha256', 'route_sha256', 'weather_sha256',
            'camera_plan_sha256', 'frame_map_sha256')}
        fixed['map_sha256'] = map_hash
        rows = [dict(fixed, case_id=case_id, original_frame=i, time_s=i / 20,
            source_sha256='raw', body_footprint_source_sha256='body',
            sign_physically_present=True, sign_text_readback='FIRE LANE',
            activity_observation='parked', attended_observation=attended,
            property_kind='public', posted_interval_m=[10, 30],
            body_interval_m=[11, 15], exception_kind='none',
            camera_frames={name: {'original_frame': i, 'source_sha256': 'a' * 64}
                for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}) for i in range(900)]
        path = root / (suffix + '.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return {'case_id': case_id, 'history_path': str(path),
                'history_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'site_sha256': fixed['site_sha256']}

    def test_attendance_pair_and_fixed_source_tampering(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            left = self.source(root, 'public_park_attended', True)
            right = self.source(root, 'public_park_unattended', False)
            audit = audit_pair(plan, 'attendance_public', left, right)
            self.assertEqual(audit['deliberate_difference'], 'attended')
            self.assertIsNone(audit['legal_judgment'])
            right = self.source(root, 'public_park_unattended', False, 'changed')
            with self.assertRaisesRegex(ValueError, 'fixed original source changed'):
                audit_pair(plan, 'attendance_public', left, right)


if __name__ == '__main__':
    unittest.main()
