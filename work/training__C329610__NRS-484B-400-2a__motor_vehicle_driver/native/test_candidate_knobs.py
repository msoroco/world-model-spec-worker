import unittest
from engineering import parameters


class CandidateKnobsTest(unittest.TestCase):
    def test_three_distinct_fallback_mechanisms_preserve_case_context(self):
        for suffix in ("controlled_1","controlled_2"):
            with self.subTest(case=suffix):
                plans={name:parameters(suffix,name) for name in
                       ("primary","fallback1","fallback2","fallback3")}
                common=("law_id","cell_id","actor","duration_s","rate_hz","comparison_lateral_m")
                for key in common:
                    self.assertEqual({str(p[key]) for p in plans.values()},{str(plans["primary"][key])})
                base=plans["primary"]
                self.assertNotEqual(plans["fallback1"]["native_route_xy_m"],base["native_route_xy_m"])
                self.assertEqual(plans["fallback1"]["controller_knobs"],base["controller_knobs"])
                self.assertEqual(plans["fallback1"]["cameras"],base["cameras"])
                self.assertEqual(plans["fallback2"]["native_route_xy_m"],base["native_route_xy_m"])
                self.assertNotEqual(plans["fallback2"]["controller_knobs"],base["controller_knobs"])
                self.assertEqual(plans["fallback2"]["cameras"],base["cameras"])
                self.assertEqual(plans["fallback3"]["native_route_xy_m"],base["native_route_xy_m"])
                self.assertEqual(plans["fallback3"]["controller_knobs"],base["controller_knobs"])
                self.assertNotEqual(plans["fallback3"]["cameras"],base["cameras"])


if __name__=="__main__":unittest.main()
