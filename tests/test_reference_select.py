import unittest

from reference_select import select


class ReferenceSelectionTests(unittest.TestCase):
    def test_exact_law_takes_precedence_over_generic_travel(self):
        result=select('testing__C147311__NRS-484B-220-1__motor_vehicle_driver')
        self.assertEqual({r['cell'] for r in result['references']},{'C150916'})

    def test_stop_sign_reference_is_not_testing_evidence(self):
        result=select('testing__C158208__NRS-484B-257-1__motor_vehicle_driver')
        self.assertIn('C111325',{r['cell'] for r in result['references']})
        self.assertIn('not test evidence',result['references'][0]['role'])


if __name__=='__main__':
    unittest.main()
