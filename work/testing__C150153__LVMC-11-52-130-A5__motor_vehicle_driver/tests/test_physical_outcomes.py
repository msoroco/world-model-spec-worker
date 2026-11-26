"""Synthetic original-history shapes test physical checker states only."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from parking import CASES
from physical_outcomes import LIFECYCLE, evaluate, verify_lifecycle
from test_native_history_capture import Adapter
from test_parking import site


class PhysicalOutcomeTests(unittest.TestCase):
    def test_complete_incomplete_missing_for_exact_case_matrix(self):
        original_site = site()
        original_site['site_sha256'] = 'diagnostic-site-source'
        for case in CASES:
            with self.subTest(case=case.id):
                adapter = Adapter(original_site, case)
                rows = [adapter.tick_and_sample() for _ in range(900)]
                complete = evaluate(case, rows, original_site, 'diagnostic-history-source',
                                    original_site['site_sha256'], diagnostic_fixture=True)
                self.assertEqual(complete['physical_checks']['maneuver']['status'], 'met')
                self.assertTrue(complete['maneuver_completed'])
                self.assertIsNone(complete['legal_judgment'])
                changed = [dict(row, activity_observation='moving') for row in rows]
                incomplete = evaluate(case, changed, original_site, 'diagnostic-history-source',
                                      original_site['site_sha256'], diagnostic_fixture=True)
                self.assertEqual(incomplete['physical_checks']['maneuver']['status'], 'not_met')
                missing = evaluate(case, None, original_site, None,
                                   original_site['site_sha256'], diagnostic_fixture=True)
                self.assertEqual(missing['physical_checks']['maneuver']['status'], 'unverified')
                self.assertFalse(missing['maneuver_completed'])

    def test_lifecycle_requires_release_before_saved_processing(self):
        self.assertTrue(verify_lifecycle(LIFECYCLE))
        changed = list(LIFECYCLE)
        changed[-1], changed[-2] = changed[-2], changed[-1]
        with self.assertRaisesRegex(ValueError, 'precedes Native ownership closure'):
            verify_lifecycle(changed)


if __name__ == '__main__':
    unittest.main()
