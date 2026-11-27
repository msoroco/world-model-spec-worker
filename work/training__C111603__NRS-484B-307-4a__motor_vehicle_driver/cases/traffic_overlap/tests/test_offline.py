import unittest
from runner import check
from survey import load

class GreenArrowSelectedTest(unittest.TestCase):
    def test_exact_controller_branches(self):
        result=check()
        self.assertEqual(result['exact_cases_checked'],8)
        self.assertFalse(result['native_executed'])
        self.assertEqual(result['controller_phases']['pedestrian_yield'],'pause_for_observed_pedestrian')
        self.assertEqual(result['controller_phases']['traffic_yield'],'pause_for_observed_traffic')

    def test_original_governing_survey_required(self):
        with self.assertRaisesRegex(ValueError,'Original governed-arrow intersection survey required'):
            load('/unavailable/original-survey.json','case__direction_indicated')

if __name__=='__main__':
    unittest.main()
