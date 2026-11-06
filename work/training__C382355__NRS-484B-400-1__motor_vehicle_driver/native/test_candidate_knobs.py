import unittest
from engineering import parameters


class CandidateKnobsTest(unittest.TestCase):
    def test_fallbacks_change_separate_knobs_and_hold_case_context(self):
        for suffix in ('witness_1','witness_2'):
            plans={name:parameters(suffix,name) for name in
                   ('primary','fallback1','fallback2','fallback3')}
            base=plans['primary']
            for name,plan in plans.items():
                self.assertEqual(plan['native_route_xy_m'],
                                 [[x,-y] for x,y in plan['authored_route_xy_m']])
                self.assertEqual(plan['native_route_xy_m'][0][1],
                                 -plan['comparison_approach_y_m'])
                self.assertGreater(plan['native_route_xy_m'][-1][1],7)
                for key in ('law_id','cell_id','actor','duration_s','rate_hz','comparison_approach_y_m'):
                    self.assertEqual(plan[key],base[key],(suffix,name,key))
            self.assertNotEqual(plans['fallback1']['native_route_xy_m'],base['native_route_xy_m'])
            self.assertEqual(plans['fallback1']['controller_knobs'],base['controller_knobs'])
            self.assertEqual(plans['fallback1']['cameras'],base['cameras'])
            self.assertEqual(plans['fallback2']['native_route_xy_m'],base['native_route_xy_m'])
            self.assertNotEqual(plans['fallback2']['controller_knobs'],base['controller_knobs'])
            self.assertEqual(plans['fallback2']['cameras'],base['cameras'])
            self.assertEqual(plans['fallback3']['native_route_xy_m'],base['native_route_xy_m'])
            self.assertEqual(plans['fallback3']['controller_knobs'],base['controller_knobs'])
            self.assertNotEqual(plans['fallback3']['cameras'],base['cameras'])


if __name__=='__main__':unittest.main()
