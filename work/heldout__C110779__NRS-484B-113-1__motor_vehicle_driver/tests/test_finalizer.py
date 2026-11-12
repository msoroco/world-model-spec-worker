import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backing_finalizer import analyze,PREFIX,CAMERAS

class FinalizerTests(unittest.TestCase):
    def setup(self,root):
        config={'selected_case_id':PREFIX+'backing_clear_vehicle','law_id':'NRS-484B-113-1',
                'cell_id':'C110779','actor':'motor_vehicle_driver'}
        (root/'config.json').write_text(json.dumps(config))
        corridor=b'{"format":"synthetic-backing-corridor"}\n'
        (root/'backing_corridor_original.json').write_bytes(corridor)
        (root/'backing_context.json').write_text(json.dumps({'corridor_source_sha256':hashlib.sha256(corridor).hexdigest(),'participants':{'2':{
            'kind':'vehicle','position_motion_purpose_source':'Native readback plus authored purpose',
            'highway_use_source':'reviewed Native lane'}}}))
        motion=[];contact=[];mapping=[]
        for i in range(3):
            frame=100+i;time_s=i*.05
            motion.append({'frame':frame,'time_s':time_s,
                'ego':{'x_m':10-i,'y_m':0,'body_radius_m':1},
                'ego_heading_xy':[1,0],'ego_velocity_xy':[-1,0],
                'participants':{'2':{'x_m':5,'y_m':0,'body_radius_m':1,'speed_mps':1}}})
            contact.append({'frame':frame,'time_s':time_s,'contact_actor_ids':[]})
            mapping.append({'carla_frame':frame,'time_s':time_s})
        for name,rows in [('backing_motion.jsonl',motion),('backing_contacts.jsonl',contact),('video_frames.jsonl',mapping)]:
            (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        for camera in CAMERAS:(root/(camera+'.mkv')).write_bytes(b'fixture placeholder')
    def test_original_sources_analyzed_without_legal_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.setup(root);result=analyze(root)
            self.assertEqual(result['measurements']['backing_safety_observation']['value']['backing_onset_frame'],100)
            self.assertFalse(result['legal_acceptance_claimed'])
    def test_missing_camera_or_changed_frame_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.setup(root);(root/'overview.mkv').unlink()
            with self.assertRaisesRegex(ValueError,'camera source'):analyze(root)
            (root/'overview.mkv').write_bytes(b'fixture placeholder')
            mapping=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
            mapping[1]['carla_frame']=999
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in mapping))
            with self.assertRaisesRegex(ValueError,'frame map'):analyze(root)
if __name__=='__main__':unittest.main()
