import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from saved_audit import audit_planned_case


class PlannedSourceAuditTests(unittest.TestCase):
    def rows(self, suffix, activity='parked', attended=True, overlap=True):
        fixed = {key: key + '-source' for key in (
            'ego_id', 'sign_id', 'site_sha256', 'map_sha256',
            'jurisdiction_sha256', 'fire_code_designation_sha256',
            'posting_authority_sha256', 'posted_extent_sha256',
            'sign_identity_sha256', 'sign_appearance_sha256',
            'property_source_sha256', 'curb_geometry_sha256',
            'route_sha256', 'weather_sha256',
            'camera_plan_sha256', 'frame_map_sha256')}
        case_id = ROOT.name + '__' + suffix
        rows = []
        for i in range(900):
            rows.append(dict(fixed, case_id=case_id, original_frame=i,
                time_s=i / 20, source_sha256='raw',
                body_footprint_source_sha256='body',
                sign_physically_present=True, sign_text_readback='FIRE LANE',
                activity_observation=activity, attended_observation=attended,
                property_kind='public', posted_interval_m=[10, 30],
                body_interval_m=[11, 15] if overlap else [31, 35],
                camera_frames={name: {'original_frame': i, 'source_sha256': 'a' * 64}
                    for name in ('overview', 'approach', 'reference_corner', 'driver_reference')},
                exception_kind='none'))
        return rows, fixed['site_sha256'], case_id

    def audit(self, rows, site_sha, case_id):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory) / 'history.jsonl'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return audit_planned_case(path, digest, case_id, site_sha)

    def test_hold_must_realize_planned_variation(self):
        rows, site_sha, case_id = self.rows('public_park_attended')
        self.assertEqual(self.audit(rows, site_sha, case_id)['observed']['hold_overlap_frames'], 100)
        rows[-1]['activity_observation'] = 'moving'
        with self.assertRaisesRegex(ValueError, 'planned activity'):
            self.audit(rows, site_sha, case_id)
        rows[-1]['activity_observation'] = 'parked'
        rows[-1]['attended_observation'] = False
        with self.assertRaisesRegex(ValueError, 'planned attendance'):
            self.audit(rows, site_sha, case_id)

    def test_outside_rejects_overlap(self):
        rows, site_sha, case_id = self.rows('outside_posted_extent', overlap=False)
        self.assertEqual(self.audit(rows, site_sha, case_id)['observed']['hold_overlap_frames'], 0)
        rows[-1]['body_interval_m'] = [11, 15]
        with self.assertRaisesRegex(ValueError, 'planned outside'):
            self.audit(rows, site_sha, case_id)


if __name__ == '__main__':
    unittest.main()
