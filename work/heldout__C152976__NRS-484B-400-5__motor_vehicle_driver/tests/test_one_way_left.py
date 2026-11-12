import importlib.util
from pathlib import Path
import sys
import unittest
spec=importlib.util.spec_from_file_location('one_way_left',Path(__file__).resolve().parents[1]/'one_way_left.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
class Fake:
    def __init__(self):self.calls=[]
    def one_way_intersection(self,**kw):self.calls.append(('roads',kw));return kw
    def vehicle(self,**kw):self.calls.append(('vehicle',kw));return kw
class TurnTest(unittest.TestCase):
    def test_one_way_geometry_and_turn_created(self):
        for case in m.CASES.values():
            f=Fake();scene=m.construct(f,case)
            self.assertEqual(scene['roads']['approach_direction'],'north')
            self.assertEqual(scene['roads']['departure_direction'],'west')
            self.assertEqual(scene['ego']['maneuver'],'left_turn')
            p=scene['route']
            self.assertEqual(p[0][0],case.approach_center_x)
            self.assertEqual(p[-1][1],case.departure_center_y)
            self.assertTrue(all(p[i+1][0]<=p[i][0]+1e-9 for i in range(1,len(p)-1)))
            self.assertTrue(all(p[i+1][1]>=p[i][1]-1e-9 for i in range(1,len(p)-2)))
    def samples(self):
        return [{'time_s':0,'native_road_direction':'north','body_corners_xy':[[-5.4,-20],[-3.6,-20],[-3.6,-16],[-5.4,-16]],'observed_left_curb_x':-6,'source':'native/footprints.jsonl'},
                {'time_s':.5,'native_road_direction':'turn','body_corners_xy':[[-5.4,-5.4],[-3.6,-5.4],[-3.6,-3.6],[-5.4,-3.6]],'turn_left_edge_polyline_xy':[[-6,-10],[-6,-6],[-10,-6]],'source':'native/footprints.jsonl'},
                {'time_s':1,'native_road_direction':'west','body_corners_xy':[[-20,-5.4],[-16,-5.4],[-16,-3.6],[-20,-3.6]],'observed_left_curb_y':-6,'source':'native/footprints.jsonl'}]
    def test_independent_approach_and_departure_measurement(self):
        r=m.measure(self.samples())
        self.assertAlmostEqual(r['minimum_approach_gap_m'],.6)
        self.assertAlmostEqual(r['minimum_departure_gap_m'],.6)
        self.assertGreater(r['minimum_turn_gap_m'],0)
        self.assertEqual(r['legal_practicability_judgment'],'unresolved')
        same=self.samples()[:1]*2; same[1]=dict(same[1],time_s=1)
        with self.assertRaisesRegex(ValueError,'all required'):m.measure(same)
    def test_comparison_checks_fixed_and_declared_differences(self):
        a=dict(samples=[1],map_hash='m',curb_geometry_hash='c',road_directions=['north','west'],
               controller_policy_hash='p',camera_plan_hash='v',duration_s=8,
               approach_center_x=-4.5,departure_center_y=-4.5)
        b=dict(a,approach_center_x=-3.5)
        self.assertTrue(m.audit_comparison(a,b,['approach_center_x'])['fixed_conditions_checked'])
        with self.assertRaisesRegex(ValueError,'fixed condition'):m.audit_comparison(a,dict(b,map_hash='x'),['approach_center_x'])
        with self.assertRaisesRegex(ValueError,'undeclared'):m.audit_comparison(a,b,['departure_center_y'])
if __name__=='__main__':unittest.main()
