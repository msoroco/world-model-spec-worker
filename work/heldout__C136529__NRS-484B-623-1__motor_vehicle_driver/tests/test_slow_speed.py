import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('slow_speed',Path(__file__).resolve().parents[1]/'slow_speed.py')
module=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=module
spec.loader.exec_module(module)

class Fake:
    def __init__(self): self.calls=[]
    def narrow_road(self,**kw): self.calls.append(('road',kw)); return kw
    def vehicle(self,**kw): self.calls.append(('vehicle',kw)); return kw
    def prop(self,**kw): self.calls.append(('prop',kw)); return kw

class SlowSpeedTest(unittest.TestCase):
    def test_construction_creates_both_approaches_and_real_props(self):
        for name,case in module.CASES.items():
            a=Fake(); scene=module.construct(a,case)
            self.assertEqual(len([c for c in a.calls if c[0]=='vehicle']),3)
            self.assertEqual(scene['ego']['route'][0][1],-65)
            self.assertEqual(scene['opposing']['route'][0][1],65)
            self.assertEqual(len(scene['props']),int(case.obstruction)+int(case.regulatory_control))
            if case.obstruction: self.assertEqual(scene['props'][0]['kind'],'parked_vehicle')
    def samples(self):
        return [{'time_s':i*.05,'ego_valid':True,'follower_valid':True,'opposing_valid':True,
                 'ego_xy':(0,i*.15),'follower_xy':(0,-20+i*.2),'opposing_xy':(0,70-i*.4),
                 'ego_speed_mps':3,'follower_speed_mps':4,'source':'native/actors.jsonl'} for i in range(3)]
    def test_measure_requires_synchronized_observations(self):
        result=module.measure(self.samples())
        self.assertEqual(result['legal_judgment'],'unresolved')
        bad=self.samples();bad[1]['follower_valid']=False
        with self.assertRaisesRegex(ValueError,'missing observed participant'): module.measure(bad)
        bad=self.samples();bad[1]['time_s']=0.07
        with self.assertRaisesRegex(ValueError,'non-20Hz'): module.measure(bad)
    def test_audit_rejects_missing_and_undeclared_changes(self):
        x=dict(samples=[1],map_hash='m',lane_width_m=2.75,weather='dry',camera_plan_hash='c',duration_s=8,
               ego_target_mps=8,obstruction=False,regulatory_control=False)
        y=dict(x,ego_target_mps=3)
        self.assertTrue(module.audit_comparison(x,y,['ego_target_mps'])['measured_only'])
        with self.assertRaisesRegex(ValueError,'difference'): module.audit_comparison(x,y,[])
        with self.assertRaisesRegex(ValueError,'fixed condition'): module.audit_comparison(x,dict(y,weather='rain'),['ego_target_mps'])
        with self.assertRaisesRegex(ValueError,'missing measured'): module.audit_comparison(x,dict(y,samples=[]),['ego_target_mps'])

if __name__=='__main__': unittest.main()
