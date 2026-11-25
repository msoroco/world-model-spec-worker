"""Contract tests; report dictionaries here are mock-only, never evidence."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from delivery_audit import audit_attempt, audit_comparisons
from sidewalk_overtake import ASSIGNMENT


class DeliveryAuditTests(unittest.TestCase):
    def reports(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        result = {}
        for item in plan['cases']:
            cid = item['case_id']
            name = cid.removeprefix(ASSIGNMENT + '__')
            before = 'late' not in name and 'silent' not in name
            brakes = [] if 'advance' in name else [5]
            hashes = {'road.xodr': 'a' * 64, 'site-context.json': 'b' * 64}
            measurement = {
                'format': 'worker-c142510-sidewalk-overtake-v1',
                'assignment_id': ASSIGNMENT, 'case_id': cid,
                'sidewalk_id': 'MOCK ONLY', 'rider_kind': item['rider_kind'],
                'frame_count': 900, 'detected_signal_before_pass': before,
                'brake_frames_before_pass': brakes, 'source_sha256': hashes}
            result[cid] = {
                'format': 'c142510-independent-original-audit-v1',
                'case_id': cid, 'source_kind': 'original_native_capture',
                'source_sha256': hashes,
                'fixed_site': {'sidewalk_id': 'MOCK ONLY'},
                'rider_kind': item['rider_kind'], 'measurement': measurement,
                'legal_status': 'unresolved', 'physical_acceptance': False}
        return result

    def test_three_exact_comparison_contracts(self):
        self.assertEqual(len(audit_comparisons(self.reports())), 3)

    def test_fixed_source_change_rejected(self):
        reports = self.reports()
        key = ASSIGNMENT + '__bicycle_signal_late_yield'
        reports[key]['fixed_site'] = {'sidewalk_id': 'different'}
        with self.assertRaisesRegex(ValueError, 'fixed original sidewalk'):
            audit_comparisons(reports)

    def test_synthetic_provenance_rejected(self):
        reports = self.reports()
        key = ASSIGNMENT + '__bicycle_signal_late_yield'
        reports[key]['source_kind'] = 'synthetic_fixture'
        with self.assertRaisesRegex(ValueError, 'nonoriginal'):
            audit_comparisons(reports)

    def test_missing_original_attempt_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original attempt missing'):
            audit_attempt(ROOT / 'no-original-attempt',
                          ASSIGNMENT + '__bicycle_signal_before_yield')


if __name__ == '__main__':
    unittest.main()
