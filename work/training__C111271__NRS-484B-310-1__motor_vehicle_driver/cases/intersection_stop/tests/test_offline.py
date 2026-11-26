import unittest
from controller import State, command
from runner import check
from capture import survey_for


class ExactFlashingRedTest(unittest.TestCase):
    def test_exact_bundle_and_controller(self):
        result = check()
        self.assertEqual(result['exact_cases_checked'], 6)
        self.assertFalse(result['native_executed'])
        for stop, no_stop, reference in (
                ('probe_a', 'probe_b', 48.0),
                ('crosswalk_stop', 'crosswalk_no_stop', 50.0),
                ('intersection_stop', 'intersection_no_stop', 52.0)):
            self.assertEqual(command(stop, reference - 2, 5, reference, False, State())['engineering_phase'], 'pre_reference_stop')
            self.assertEqual(command(no_stop, reference - 2, 5, reference, False, State())['engineering_phase'], 'proceed')

    def test_missing_original_survey_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Original Native context survey required'):
            survey_for('case__probe_a', '/unavailable/original-survey.json')


if __name__ == '__main__':
    unittest.main()
