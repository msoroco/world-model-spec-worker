import json
import sys
import tempfile
from pathlib import Path
import unittest

folder=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(folder))
from slow_finalizer import analyze

class SavedSourceTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        frames=[];actors=[];props=[]
        for i in range(3):
            t=i*.05; f=100+i
            frames.append({'video_frame':i,'carla_frame':f,'time_s':t})
            actors.append({'frame':f,'time_s':t,'ego_valid':True,'follower_valid':True,
                           'opposing_valid':True,'ego_xy':[0,i*.15],
                           'follower_xy':[0,-20+i*.2],'opposing_xy':[0,70-i*.4],
                           'ego_speed_mps':3,'follower_speed_mps':4})
            props.append({'frame':f,'time_s':t,'obstruction_present':True,'obstruction_geometry':{'vertices_xyz':[[0,0,0]]*4},
                          'obstruction_visible':True,'control_present':False})
        self.write('video_frames.jsonl',frames)
        self.write('participant_state.jsonl',actors)
        self.write('trace.jsonl',[{'frame':100+i,'time_s':i*.05} for i in range(3)])
        (self.root/'config.json').write_text(json.dumps({'law_id':'NRS-484B-623-1','cell_id':'C136529','actor':'motor_vehicle_driver','selected_case_id':'heldout__C136529__NRS-484B-623-1__motor_vehicle_driver__slow_for_obstruction','ego_target_mps':3,'case':{'recording_description':{'channels':[]}}}))
        self.write('prop_state.jsonl',props)
        (self.root/'slow_context.json').write_text(json.dumps({'case_branch':'slow_for_obstruction'}))
    def write(self,n,rows):
        (self.root/n).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    def test_positive_joins_and_measures(self):
        r=analyze(self.root)
        self.assertAlmostEqual(r['measurements']['slow_speed_observation']['value']['minimum_follower_gap_m'],19.9)
        self.assertFalse(r['physical_acceptance_claimed'])
        from slow_finalizer import build_result
        native=build_result(self.root,r)
        self.assertEqual(len(native['recording_evidence']),3)
    def test_cli_writes_native_result_and_rejects_missing_source(self):
        import os
        import subprocess
        runtime=folder.parents[1]/'runtime'
        env=dict(os.environ,PYTHONPATH=str(runtime/'scenario_pipeline')+os.pathsep+str(runtime))
        command=[sys.executable,str(folder/'slow_finalizer.py'),'--attempt',str(self.root),
                 '--output',str(self.root/'analysis-report.json')]
        good=subprocess.run(command,capture_output=True,text=True,env=env)
        self.assertEqual(good.returncode,0,good.stderr)
        self.assertTrue((self.root/'result.json').is_file())
        (self.root/'analysis-report.json').unlink()
        (self.root/'result.json').unlink()
        (self.root/'prop_state.jsonl').unlink()
        bad=subprocess.run(command,capture_output=True,text=True,env=env)
        self.assertNotEqual(bad.returncode,0)
        self.assertIn('Missing required source: prop_state.jsonl',bad.stderr)

    def test_rejects_missing_original_source(self):
        (self.root/'participant_state.jsonl').unlink()
        with self.assertRaisesRegex(ValueError,'Missing required source'):
            analyze(self.root)
    def test_rejects_mismatched_frame_and_missing_physical_feature(self):
        p=self.root/'prop_state.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
        rows[1]['frame']=999;self.write('prop_state.jsonl',rows)
        with self.assertRaisesRegex(ValueError,'original frame/time join'): analyze(self.root)
        rows[1]['frame']=101; rows[1]['obstruction_present']=False
        self.write('prop_state.jsonl',rows)
        with self.assertRaisesRegex(ValueError,'physical obstruction missing'): analyze(self.root)

if __name__=='__main__': unittest.main()
