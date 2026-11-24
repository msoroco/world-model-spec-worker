import unittest
from engineering import parameters


class CandidateKnobsTest(unittest.TestCase):
    def test_distinct_fallbacks_hold_exit_comparison_fixed(self):
        for suffix in ("witness_1", "witness_2"):
            plans={name:parameters(suffix,name) for name in
                   ("primary","fallback1","fallback2","fallback3")}
            baseline=plans["primary"]
            for name,plan in plans.items():
                for key in ("law_id","cell_id","actor","duration_s","rate_hz","comparison_exit_x_m"):
                    self.assertEqual(plan[key],baseline[key],(suffix,name,key))
            self.assertNotEqual(plans["fallback1"]["native_route_xy_m"],baseline["native_route_xy_m"])
            self.assertEqual(plans["fallback1"]["controller_knobs"],baseline["controller_knobs"])
            self.assertEqual(plans["fallback1"]["cameras"],baseline["cameras"])
            self.assertEqual(plans["fallback2"]["native_route_xy_m"],baseline["native_route_xy_m"])
            self.assertNotEqual(plans["fallback2"]["controller_knobs"],baseline["controller_knobs"])
            self.assertEqual(plans["fallback2"]["cameras"],baseline["cameras"])
            self.assertEqual(plans["fallback3"]["native_route_xy_m"],baseline["native_route_xy_m"])
            self.assertEqual(plans["fallback3"]["controller_knobs"],baseline["controller_knobs"])
            self.assertNotEqual(plans["fallback3"]["cameras"],baseline["cameras"])


if __name__ == "__main__":unittest.main()
