"""CPU checks for the exact straight-arrow/yield construction."""
import unittest
from pathlib import Path

from engineering import CASES, KNOBS, parameters
from measure import measure_arrow_and_yield, joined_samples


class ExactConstructionTests(unittest.TestCase):
    def test_all_case_candidate_pairs_keep_boolean_branch_and_distinct_knobs(self):
        for case_id, expected in CASES.items():
            variants = [parameters(case_id, name) for name in KNOBS]
            self.assertEqual(len(variants), 4)
            self.assertEqual(len({str(v['knobs']) for v in variants}), 4)
            for variant in variants:
                self.assertIs(variant['lawful_conflict_participant_present'], expected)
                self.assertEqual(variant['rate_hz'] * variant['duration_s'], 840)

    def test_unknown_case_and_candidate_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown exact case'):
            parameters('outside_scope', 'primary')
        with self.assertRaisesRegex(ValueError, 'Unknown exact case'):
            parameters(next(iter(CASES)), 'outside_scope')

    def test_missing_original_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing original source'):
            joined_samples(Path('/nonexistent-straight-arrow-attempt'))

    def test_arrow_measurement_rejects_absent_source_frames(self):
        with self.assertRaisesRegex(ValueError, 'No original samples'):
            measure_arrow_and_yield([])


if __name__ == '__main__':
    unittest.main()
