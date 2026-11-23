import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / 'saved_audit.py'
spec = importlib.util.spec_from_file_location('trail_saved_audit', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def rows(case='all_prerequisites', n=900):
    base = dict(case_id=case, cell_id='C143687', map_sha256='map',
                corridor_source_sha256='corridor', route_sha256='route',
                vehicle_blueprint='vehicle.test', operator_source_sha256='operator',
                camera_plan_sha256='camera', duration_frames=900,
                official_plan_designation=True, city_trail_dedication=True,
                prohibits_motor_vehicles=True, emergency_use=False,
                maintenance_use=False, sign_face_sha256='face',
                governed_access_sha256='access', official_plan_source_sha256='plan',
                dedication_source_sha256='deed', exception_status_source_sha256='status',
                vehicle_id='ego', operator_id='driver', native_packet_sha256='packet')
    return [dict(base, original_frame=i, vehicle_inside_corridor=i > 10,
                 sign_face_visible=i == 12) for i in range(n)]


def run(rows_):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'native.jsonl'
        raw = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows_).encode()
        path.write_bytes(raw)
        return audit.audit_history(path, hashlib.sha256(raw).hexdigest(), rows_[0]['case_id'])


class SavedAuditTests(unittest.TestCase):
    def test_source_bound_full_history(self):
        result = run(rows())
        self.assertEqual(result['frame_count'], 900)
        self.assertTrue(result['entered_corridor'])
        self.assertIsNone(result['legal_judgment'])

    def test_reject_missing_or_changed_native_source(self):
        values = rows()
        values[7]['native_packet_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'Native actor source missing'):
            run(values)
        values = rows()
        values[8]['route_sha256'] = 'other'
        with self.assertRaisesRegex(ValueError, 'fixed source changed'):
            run(values)

    def test_reject_short_or_discontinuous_history(self):
        with self.assertRaisesRegex(ValueError, 'frame count'):
            run(rows(n=899))
        values = rows()
        values[4]['original_frame'] = 9
        with self.assertRaisesRegex(ValueError, 'frame join'):
            run(values)

    def test_compare_only_declared_difference(self):
        left = run(rows())
        altered = rows('not_designated')
        for row in altered:
            row['official_plan_designation'] = False
        right = run(altered)
        result = audit.audit_pair(left, right, 'official_plan_designation')
        self.assertEqual(result['difference'], 'official_plan_designation')
        right['map_sha256'] = 'new-map'
        with self.assertRaisesRegex(ValueError, 'fixed condition changed'):
            audit.audit_pair(left, right, 'official_plan_designation')


if __name__ == '__main__':
    unittest.main()
