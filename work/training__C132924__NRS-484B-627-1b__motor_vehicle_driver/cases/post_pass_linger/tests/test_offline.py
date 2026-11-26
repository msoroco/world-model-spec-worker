import unittest
from runner import check
from capture import survey_for

class ExactRoundaboutTest(unittest.TestCase):
    def test_four_source_driven_branches(self):
        result = check()
        self.assertEqual(result['exact_cases_checked'], 4)
        self.assertFalse(result['native_executed'])
        self.assertEqual(result['controller_phases']['necessary_pass_after_clearance'], 'return_after_pass')
        self.assertEqual(result['controller_phases']['post_pass_linger_after_clearance'], 'linger_after_pass')

    def test_original_survey_required(self):
        with self.assertRaisesRegex(ValueError, 'Original Native roundabout context survey required'):
            survey_for('case__probe_a', '/unavailable/original-survey.json')

if __name__ == '__main__':
    unittest.main()
