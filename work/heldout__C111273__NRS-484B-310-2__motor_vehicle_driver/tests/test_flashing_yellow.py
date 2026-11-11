import importlib.util
from pathlib import Path
import sys
import unittest
spec=importlib.util.spec_from_file_location('flashing_yellow',Path(__file__).resolve().parents[1]/'flashing_yellow.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
class Fake:
    def __init__(self):self.calls=[]
    def intersection(self,**kw):self.calls.append(('intersection',kw));return kw
    def signal_head(self,**kw):self.calls.append(('signal_head',kw));return kw
    def official_control_device(self,**kw):self.calls.append(('official_device',kw));return kw
    def vehicle(self,**kw):self.calls.append(('vehicle',kw));return kw
class TestFlash(unittest.TestCase):
    def test_both_approaches_create_actual_head_and_device(self):
        for case in mod.CASES.values():
            f=Fake();scene=mod.construct(f,case)
            self.assertEqual([x[0] for x in f.calls[:3]],['intersection','signal_head','official_device'])
            self.assertEqual(scene['signal_head']['governs_approach'],case.direction)
            self.assertEqual(scene['ego']['route'][0][0],-70 if case.direction=='east' else 70)
            self.assertEqual(scene['crossing'] is not None,case.crossing_vehicle)
    def test_lamp_timing_is_intermittent(self):
        self.assertEqual([mod.lamp_on(i*.05) for i in range(10)], [True]*5+[False]*5)
    def samples(self):
        return [{'time_s':i*.05,'signal_head_visible':True,'yellow_lens_on':i<5,
                 'official_device_source':'authored local control record','ego_valid':True,
                 'ego_center_xy':[20-i,0],'ego_speed_mps':4,'source':'native/signal.jsonl'} for i in range(10)]
    def test_measure_rejects_unobserved_light_and_missing_source(self):
        self.assertEqual(mod.measure(self.samples())['legal_caution_judgment'],'unresolved')
        bad=self.samples();bad[0]['official_device_source']=''
        with self.assertRaisesRegex(ValueError,'lacks source'):mod.measure(bad)
        bad=self.samples();bad[6]['yellow_lens_on']=True
        for s in bad:s['yellow_lens_on']=True
        with self.assertRaisesRegex(ValueError,'no observed intermittent'):mod.measure(bad)
    def test_comparison_rejects_changed_fixed_condition(self):
        a=dict(samples=[1],map_hash='m',signal_head_hash='s',official_device_source='d',
               blink_period_s=.5,camera_plan_hash='c',duration_s=8,
               approach_target_mps=4,crossing_vehicle=True,direction='east')
        b=dict(a,approach_target_mps=9)
        self.assertTrue(mod.audit_comparison(a,b,['approach_target_mps'])['fixed_conditions_checked'])
        with self.assertRaisesRegex(ValueError,'fixed condition'):mod.audit_comparison(a,dict(b,map_hash='x'),['approach_target_mps'])
        with self.assertRaisesRegex(ValueError,'deliberate difference'):mod.audit_comparison(a,b,[])
if __name__=='__main__':unittest.main()
