import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_bus_response import measure, audit_motion_comparison
from school_bus_controller import BRANCHES, target, apply


def corners(x):
    return [[x-1,-.5],[x+1,-.5],[x+1,.5],[x-1,.5]]


class SourceResponse(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.context={'bus_id':'bus','subject_id':'car','approach':'meeting',
                      'bus_stopped':True,'pupil_stop_purpose':True,'signs_equipped':True,
                      'divided_other_roadway':False,'traffic_officer_control':False}
        self.signal=[];self.motion=[]
        for i,(active,phase,speed,x) in enumerate(zip(
            (False,True,True,True,False,False),
            (False,True,False,True,False,False),
            (5,5,0,0,2,3),
            (-6,-5,-4,-3,-2,4))):
            self.signal.append({'frame':100+i,'time_s':i*.05,'bus_id':'bus',
                'red_signal_operating':active,'red_phase_on':phase,
                'front_red_visible':phase,'rear_red_visible':phase})
            self.motion.append({'frame':100+i,'time_s':i*.05,'bus_id':'bus','subject_id':'car',
                'subject_speed_mps':speed,'subject_corners':corners(x),
                'bus_corners':corners(0),'travel_tangent_xy':[1,0]})
    def write(self):
        paths=[]
        for name,value in (('context',self.context),('signal',self.signal),('motion',self.motion)):
            path=self.root/(name+'.json');path.write_text(json.dumps(value)+'\n');paths.append(path)
        return paths
    def result(self):
        return measure(*self.write())
    def test_meeting_holds_through_red_and_passes_after_cessation(self):
        result=self.result()
        self.assertEqual((result['red_onset_frame'],result['red_cessation_frame']),(101,104))
        self.assertEqual((result['first_stop_frame'],result['first_full_body_pass_frame']),(102,105))
        self.assertTrue(result['held_stop_until_cessation'])
        self.assertIsNone(result['premature_restart_frame'])
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertIsNone(result['legal_conclusion'])
        self.assertEqual(set(result['source_sha256']),{'context','signal','motion'})
    def test_overtaking_opposite_tangent_and_premature_restart(self):
        self.context['approach']='overtaking'
        for row in self.motion:
            row['travel_tangent_xy']=[-1,0]
            row['subject_corners']=corners(-row['subject_corners'][0][0]-1)
        self.motion[3]['subject_speed_mps']=2
        result=self.result()
        self.assertEqual(result['premature_restart_frame'],103)
        self.assertFalse(result['held_stop_until_cessation'])
        self.assertEqual(result['first_full_body_pass_frame'],105)
    def test_active_red_pass_and_missing_sources(self):
        self.motion[3]['subject_corners']=corners(4)
        self.assertEqual(self.result()['first_full_body_pass_frame'],103)
        paths=self.write();paths[1].unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            measure(*paths)
    def test_rejects_signal_and_frame_contradictions(self):
        self.signal[3]['rear_red_visible']=False
        with self.assertRaisesRegex(ValueError,'front and rear'):self.result()
        self.signal[3]['rear_red_visible']=True
        self.signal[2]['red_phase_on']=True
        self.signal[2]['front_red_visible']=True
        self.signal[2]['rear_red_visible']=True
        with self.assertRaisesRegex(ValueError,'alternation'):self.result()
        self.signal[2]['red_phase_on']=False
        self.motion[2]['time_s']=.105
        with self.assertRaisesRegex(ValueError,'frames differ'):self.result()
        self.motion[2]['time_s']=.1
        self.motion[2]['subject_corners']=[[0,0]]
        with self.assertRaisesRegex(ValueError,'body corners'):self.result()

    def test_all_selected_controller_branches_and_actual_apply_call(self):
        self.assertEqual(len(BRANCHES),8)
        class Vehicle:
            applied=None
            def apply_control(self, control):self.applied=control
        vehicle=Vehicle()
        for branch in BRANCHES:
            before=target(branch,red_signal_operating=True,stop_observed=False)
            after=target(branch,red_signal_operating=True,stop_observed=True)
            if branch=='meeting_restart_before_red_ceases':
                self.assertEqual((before['target_speed_mps'],after['target_speed_mps']),(0,5))
            elif branch in ('meeting_stop','overtaking_stop','meeting_resume_after_red_ceases'):
                self.assertEqual(before['target_speed_mps'],0)
            else:
                self.assertEqual(before['target_speed_mps'],5)
            self.assertIsNone(before['legal_conclusion'])
            control=apply(vehicle,dict,before,speed_mps=5)
            self.assertEqual(vehicle.applied,control)
            if before['target_speed_mps']==0:self.assertGreater(control['brake'],0)
            self.assertEqual(target(branch,red_signal_operating=False,stop_observed=True)['target_speed_mps'],5)
        with self.assertRaisesRegex(ValueError,'Unknown school-bus branch'):
            target('invented',red_signal_operating=True,stop_observed=False)

    def test_independent_motion_comparisons_and_fixed_source_rejection(self):
        baseline=self.write()
        variant_dir=self.root/'variant';variant_dir.mkdir()
        variant=[variant_dir/p.name for p in baseline]
        for source,destination in zip(baseline,variant):destination.write_bytes(source.read_bytes())
        restart=json.loads(variant[2].read_text())
        restart[3]['subject_speed_mps']=2
        variant[2].write_text(json.dumps(restart)+'\n')
        proof=audit_motion_comparison(baseline,variant,'premature_restart')
        self.assertEqual(proof['variant']['premature_restart_frame'],103)
        self.assertFalse(proof['physical_acceptance_claimed'])
        self.assertIsNone(proof['legal_conclusion'])
        with self.assertRaisesRegex(ValueError,'lacks passage during red'):
            audit_motion_comparison(baseline,variant,'pass_during_red')
        restart[3]['subject_corners']=corners(4)
        variant[2].write_text(json.dumps(restart)+'\n')
        self.assertEqual(audit_motion_comparison(baseline,variant,'pass_during_red')
                         ['variant']['first_full_body_pass_frame'],103)
        changed=json.loads(variant[1].read_text())
        changed[3]['red_phase_on']=False
        variant[1].write_text(json.dumps(changed)+'\n')
        with self.assertRaisesRegex(ValueError,'changed fixed original'):
            audit_motion_comparison(baseline,variant,'pass_during_red')
        variant[1].unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            audit_motion_comparison(baseline,variant,'pass_during_red')

if __name__=='__main__':unittest.main()
