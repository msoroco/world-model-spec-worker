import unittest
from engineering import CANDIDATES, check, plan
from geometry import OBSERVER_DISTANCES_FT


class CandidateEngineeringTest(unittest.TestCase):
    def test_distinct_fallbacks_and_controlled_context(self):
        result = check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['construction_plans'],12)

    def test_each_case_has_four_unselected_plans(self):
        for suffix in OBSERVER_DISTANCES_FT:
            for candidate in CANDIDATES:
                with self.subTest(suffix=suffix,candidate=candidate):
                    value=plan(suffix,candidate)
                    self.assertFalse(value['selected'])
                    self.assertFalse(value['physical_trigger_measured'])

    def test_rejects_unknown_identity(self):
        with self.assertRaisesRegex(ValueError,'Unknown C104538'):
            plan('invented','primary')
        with self.assertRaisesRegex(ValueError,'Unknown C104538'):
            plan('below_500_ft','fallback4')
