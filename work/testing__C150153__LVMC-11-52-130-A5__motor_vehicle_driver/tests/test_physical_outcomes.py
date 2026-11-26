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


def with_observed_approach(rows):
    rows = [dict(row) for row in rows]
    for index in range(20):
        shift = 2.0 * (1.0 - index / 19.0)
        row = rows[index]
        row['body_west_x_m'] -= shift
        row['body_east_x_m'] -= shift
        row['ego_position_m'] = [row['ego_position_m'][0] - shift,
                                 row['ego_position_m'][1], row['ego_position_m'][2]]
        row['ego_speed_mps'] = 2.0 if index < 19 else 0.0
        row['activity_observation'] = 'moving' if index < 19 else row['activity_observation']
    return rows


class PhysicalOutcomeTests(unittest.TestCase):
    def test_complete_incomplete_missing_for_exact_case_matrix(self):
        original_site = site()
        original_site['site_sha256'] = 'diagnostic-site-source'
        for case in CASES:
            with self.subTest(case=case.id):
                adapter = Adapter(original_site, case)
                rows = [adapter.tick_and_sample() for _ in range(900)]
                static = evaluate(case, rows, original_site, 'diagnostic-history-source',
                                  original_site['site_sha256'], diagnostic_fixture=True)
                self.assertEqual(static['physical_checks']['maneuver']['status'], 'not_met')
                rows = with_observed_approach(rows)
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
                no_position = [dict(row) for row in rows]
                del no_position[400]['ego_position_m']
                unavailable = evaluate(case, no_position, original_site, 'diagnostic-history-source',
                                       original_site['site_sha256'], diagnostic_fixture=True)
                self.assertEqual(unavailable['physical_checks']['maneuver']['status'], 'unverified')

    def test_lifecycle_requires_release_before_saved_processing(self):
        self.assertTrue(verify_lifecycle(LIFECYCLE))
        changed = list(LIFECYCLE)
        changed[-1], changed[-2] = changed[-2], changed[-1]
        with self.assertRaisesRegex(ValueError, 'precedes Native ownership closure'):
            verify_lifecycle(changed)


if __name__ == '__main__':
    unittest.main()
