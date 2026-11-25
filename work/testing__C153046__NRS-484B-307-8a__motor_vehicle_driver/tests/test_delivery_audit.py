"""Independent source-custody audit of synthetic capture fixtures."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import audit
from test_analysis import AnalysisTest


class DeliveryAuditTest(AnalysisTest):
    def test_sealed_original_audit(self):
        case = self.config['selected_case_id']
        receipt = audit(self.attempt, case)
        self.assertTrue(receipt['source_custody_passed'])
        self.assertEqual(receipt['original_frames'], 900)
        self.assertTrue(receipt['diagnostic_fixture'])
        self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_reject_wrong_case_and_trace_join(self):
        with self.assertRaisesRegex(ValueError, 'case identity'):
            audit(self.attempt, 'wrong-case')
        trace = self.attempt / 'trace.jsonl'
        rows = trace.read_text().splitlines()
        first = json.loads(rows[0])
        first['time_s'] = -1
        rows[0] = json.dumps(first)
        trace.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'frame join'):
            audit(self.attempt, self.config['selected_case_id'])
