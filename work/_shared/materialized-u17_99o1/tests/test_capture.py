import unittest,tempfile,pathlib,importlib.util,json
P=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('capture_validator',P/'finalize.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CaptureTests(unittest.TestCase):
 def test_missing_capture_fails(self):
  with tempfile.TemporaryDirectory() as d:self.assertFalse(m.validate(d,{'channels':[]})['passed'])
 def test_null_mandatory_data_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'channels').mkdir();(r/'trace.jsonl').write_text(json.dumps({'frame':5,'time_s':1})+'\n');(r/'video_frame_map.jsonl').write_text(json.dumps({'video_frame':0,'carla_frame':5,'time_s':1})+'\n');(r/'channels/a.jsonl').write_text(json.dumps({'time_s':1,'value':None})+'\n');v=m.validate(r,{'channels':[{'name':'a','sampling_rate_hz':20}]});self.assertIn('unavailable mandatory evidence a',v['issues'])
 def test_frame_mismatch_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'trace.jsonl').write_text(json.dumps({'frame':5,'time_s':1})+'\n');(r/'video_frame_map.jsonl').write_text(json.dumps({'video_frame':0,'carla_frame':6,'time_s':1})+'\n');self.assertIn('frame join mismatch at 0',m.validate(r,{'channels':[]})['issues'])
