import unittest
from types import SimpleNamespace
from engineering import parameters
from geometry import TARGET_FEET
from runner import body_xy


class CandidateKnobsTest(unittest.TestCase):
    def test_native_body_vertices_are_perimeter_ordered(self):
        points=[SimpleNamespace(x=x,y=y) for x,y in
                ((2,1),(-2,-1),(2,-1),(-2,1),(2,1),(-2,-1))]
        actor=SimpleNamespace(get_transform=lambda:None,
            bounding_box=SimpleNamespace(get_world_vertices=lambda transform:points))
        polygon=body_xy(actor)
        self.assertEqual(len(polygon),4)
        area=sum(polygon[i][0]*polygon[(i+1)%4][1]-
                 polygon[(i+1)%4][0]*polygon[i][1] for i in range(4))/2
        self.assertEqual(area,8)

    def test_fallbacks_change_distinct_knobs_and_preserve_distance_request(self):
        for suffix in TARGET_FEET:
            plans={name:parameters(suffix,name) for name in
                   ('primary','fallback1','fallback2','fallback3')}
            base=plans['primary']
            for name,plan in plans.items():
                for key in ('law_id','cell_id','actor','duration_s','rate_hz',
                            'comparison_commanded_distance_ft','requested_movement'):
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
