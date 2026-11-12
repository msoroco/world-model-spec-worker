import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
REPO = next(p for p in PACKAGE.parents if (p/'runtime/scenario_pipeline').is_dir())
sys.path.insert(0, str(PACKAGE))
spec = importlib.util.spec_from_file_location('sweep_realization_audit', PACKAGE/'sweep_realization_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
BASE = REPO/'.runtime-work/c101303-full-duration/base-positive-v1/attempt'


class SweepRealizationAuditTests(unittest.TestCase):
    def test_sealed_diagnostic_has_insufficient_following(self):
        with self.assertRaisesRegex(ValueError, 'Too little original following'):
            audit.audit_point(BASE, 10.0, diagnostic_selftest=True)
        with self.assertRaisesRegex(ValueError, 'Native provenance'):
            audit.audit_point(BASE, 10.0)

    def test_wrong_commanded_gap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'engineering gap'):
            audit.audit_point(BASE, 8.5, diagnostic_selftest=True)

    def test_grid_rejects_duplicate_roots(self):
        with self.assertRaisesRegex(ValueError, 'distinct sweep captures'):
            audit.audit_grid((BASE,BASE,BASE), diagnostic_selftest=True)

    def test_grid_rejects_changed_site(self):
        points = [self.point(gap, str(i)) for i,gap in enumerate(audit.GAPS)]
        points[1]['fixed_context']['road_id'] = 42
        with patch.object(audit, 'audit_point', side_effect=points):
            with self.assertRaisesRegex(ValueError, 'road context'):
                audit.audit_grid(('a','b','c'))

    def test_grid_requires_distinct_cases_and_fixed_traffic(self):
        points = [self.point(gap, str(i)) for i,gap in enumerate(audit.GAPS)]
        points[1]['case_id'] = points[0]['case_id']
        with patch.object(audit, 'audit_point', side_effect=points):
            with self.assertRaisesRegex(ValueError, 'cases are not distinct'):
                audit.audit_grid(('a','b','c'))
        points = [self.point(gap, str(i)) for i,gap in enumerate(audit.GAPS)]
        points[2]['traffic_actor_ids'] = [1,3,4]
        with patch.object(audit, 'audit_point', side_effect=points):
            with self.assertRaisesRegex(ValueError, 'traffic participant count'):
                audit.audit_grid(('a','b','c'))

    def test_grid_rejects_changed_speed_command(self):
        points = [self.point(gap, str(i)) for i,gap in enumerate(audit.GAPS)]
        points[1]['fixed_commands']['ego_target_speed_mps'] = 5.0
        with patch.object(audit, 'audit_point', side_effect=points):
            with self.assertRaisesRegex(ValueError, 'controller conditions'):
                audit.audit_grid(('a','b','c'))

    @staticmethod
    def point(gap, suffix):
        return {'requested_engineering_gap_m':gap, 'case_id':suffix,
                'fixed_context':{'road_id':1},
                'fixed_commands':{'ego_target_speed_mps':4.0},
                'traffic_actor_ids':[1,2]}


if __name__ == '__main__':
    unittest.main()
