import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from officer_finalizer import analyze
from officer_native_runner import PREFIX

class SavedOfficerAnalysisTests(unittest.TestCase):
    def fixture(self,root):
        cid=PREFIX+'stop_responds'
        cfg={'law_id':'NRS-484B-100','cell_id':'C10365','actor':'motor_vehicle_driver','selected_case_id':cid,
             'case':{'case_id':cid,'intended_observed_response':'stopped_after_indication','recording_description':{'channels':[]}},
             'rate_hz':20,'frames':160,'direction_frame':40,'cameras':[{}]*4}
        (root/'config.json').write_text(json.dumps(cfg))
        (root/'officer_context.json').write_text(json.dumps({'actor_role':'motor_vehicle_driver','officer_role':'police_officer','officer_id':'o','subject_id':'s','duty_source':'review','lawfulness_source':'review'}))
        (root/'officer_direction.json').write_text(json.dumps({'frame':41,'officer_id':'o','subject_id':'s','command':'stop','indication_source':'four original views'}))
        history=[{'frame':f,'time_s':(f-40)*.05,'subject_id':'s','speed_mps':v,'position_m':[f*.1,0,0]}
                 for f,v in ((40,2),(41,2),(42,1),(43,0))]
        (root/'subject_motion.json').write_text(json.dumps({'frames':history}))
        (root/'subject_motion_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in history))
        (root/'video_frames.jsonl').write_text(''.join(json.dumps({'video_frame':i,'carla_frame':row['frame'],'time_s':row['time_s']})+'\n' for i,row in enumerate(history)))
        (root/'trace.jsonl').write_text(''.join(json.dumps({'frame':row['frame'],'time_s':row['time_s']})+'\n' for row in history))
    def test_source_join_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);report=analyze(root)
            self.assertEqual(report['measurements']['officer_response']['value']['observed_response'],'stopped_after_indication')
            self.assertTrue((root/'subject_speed_mps.jsonl').is_file())
            (root/'officer_direction.json').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source: officer_direction.json'):analyze(root)
    def test_original_join_rejects_changed_motion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            rows=[json.loads(line) for line in (root/'subject_motion_history.jsonl').read_text().splitlines()]
            rows[2]['frame']=99
            (root/'subject_motion_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'frame join differs'):analyze(root)

if __name__=='__main__':unittest.main()
