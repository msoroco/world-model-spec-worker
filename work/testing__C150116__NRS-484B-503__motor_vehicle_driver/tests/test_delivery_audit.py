"""Mock-only independent comparison wiring; no original capture acceptance."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from delivery_audit import ASSIGNMENT, audit_attempt, audit_comparisons
from passenger_zone import CASES


class IndependentAuditTests(unittest.TestCase):
    def reports(self):
        out = {}
        for case in CASES:
            cid = ASSIGNMENT + '__' + case.name
            out[cid] = {'format': 'c150116-independent-original-audit-v1',
                        'case_id': cid, 'source_kind': 'original_native_capture',
                        'legal_status': 'unresolved', 'physical_acceptance': False,
                        'comparison_record': {'case_id': cid, 'frame_count': 900,
                            'original_history_sha256': 'mock-history-' + case.name,
                            'site_sha256': 'mock-fixed-site',
                            'camera_plan_sha256': 'mock-four-camera-plan',
                            'zone_source_sha256': 'mock-zone',
                            'vehicle_blueprint': 'mock-car',
                            'passenger_blueprint': 'mock-passenger',
                            'conduct': case.conduct,
                            'passenger_action': case.passenger_action,
                            'release_delay_s': case.release_delay_s,
                            'regulations_effective': case.hours == 'effective'}}
        return out

    def test_four_controlled_comparisons(self):
        self.assertEqual(len(audit_comparisons(self.reports())), 4)

    def test_changed_site_rejected(self):
        reports = self.reports()
        reports[ASSIGNMENT + '__load_prompt']['comparison_record']['site_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'fixed comparison condition changed'):
            audit_comparisons(reports)

    def test_synthetic_report_rejected(self):
        reports = self.reports()
        reports[ASSIGNMENT + '__load_delayed']['source_kind'] = 'synthetic_fixture'
        with self.assertRaisesRegex(ValueError, 'nonoriginal'):
            audit_comparisons(reports)

    def test_missing_original_attempt_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original attempt missing'):
            audit_attempt(HERE / 'nonexistent-attempt', ASSIGNMENT + '__load_prompt')


if __name__ == '__main__':
    unittest.main()
