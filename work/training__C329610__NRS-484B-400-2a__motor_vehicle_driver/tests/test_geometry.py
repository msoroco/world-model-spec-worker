import unittest
from geometry import check


class GeometryTest(unittest.TestCase):
    def test_both_controlled_routes_have_supported_authored_surface(self):
        result=check()
        self.assertTrue(result['passed'])
        self.assertEqual(set(result['cases']),{'controlled_1','controlled_2'})
        self.assertEqual({v['approach_lateral_m'] for v in result['cases'].values()},
                         {-1.75,-5.25})
        self.assertFalse(result['native_verified'])


if __name__=='__main__':unittest.main()
