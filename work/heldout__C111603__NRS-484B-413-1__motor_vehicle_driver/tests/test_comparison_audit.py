import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import CHANGED, audit, load_case


class ComparisonAuditTests(unittest.TestCase):
    def test_all_five_source_bound_comparisons(self):
        for comparison_id in CHANGED:
            with self.subTest(comparison_id=comparison_id):
                report = audit(comparison_id)
                self.assertEqual(report['case_ids'], audit(comparison_id)['case_ids'])
                self.assertFalse(report['physical_acceptance_claimed'])

    def test_rejects_changed_fixed_original(self):
        pair = audit('vehicle_indicator')['case_ids']
        with self.assertRaisesRegex(ValueError, 'Fixed original comparison source differs'):
            audit('vehicle_indicator', pair[1], {'ego_turn_motion.jsonl': '{}\n'})

    def test_rejects_missing_declared_difference(self):
        pair = audit('vehicle_indicator')['case_ids']
        first, _, _ = load_case(pair[0])
        with self.assertRaisesRegex(ValueError, 'Declared original comparison difference is absent'):
            audit('vehicle_indicator', pair[1],
                  {'ego_signal_audio.jsonl': first['ego_signal_audio.jsonl']})


if __name__ == '__main__':
    unittest.main()
