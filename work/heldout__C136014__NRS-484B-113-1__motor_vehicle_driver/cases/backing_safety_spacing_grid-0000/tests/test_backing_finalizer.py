from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('backing_finalizer',Path(__file__).resolve().parents[1]/'backing_finalizer.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class FinalizerTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.p=Path(t.name)
  cfg=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
  (self.p/'config.json').write_text(json.dumps(cfg))
  maps=[];traces=[];hist=[]
  for i in range(3):
   frame=100+i;time=i*.05
   maps.append({'video_frame':i,'carla_frame':frame,'time_s':time})
   traces.append({'frame':frame,'time_s':time,'position_m':[20-i,0,0]})
   def actor(id,x):return {'actor_id':id,'position_m':[x,0,0],'speed_mps':1,
       'body_vertices_m':[[x+a,b,c] for a,b,c in ((-1,-1,0),(-1,1,0),(1,-1,0),(1,1,0),(-1,-1,2),(-1,1,2),(1,-1,2),(1,1,2))]}
   hist.append({'frame':frame,'time_s':time,'ego':actor(1,20-i),'other':actor(2,8+i),
                'ego_reverse_gear':True,'road_id':1,'lane_width_m':2.8})
  for name,rows in [('video_frames.jsonl',maps),('trace.jsonl',traces),('backing_history.jsonl',hist)]:
   (self.p/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
 def test_saved_source_measurement(self):
  report=m.analyze(self.p)
  self.assertEqual(report['measurements']['reverse_encounter']['value']['reverse_displacement_m'],2)
  result=m.result(self.p,report)
  self.assertFalse(result['setup_confirmed']);self.assertFalse(result['maneuver_completed'])
 def test_missing_case_source_and_bad_join_rejected(self):
  (self.p/'backing_history.jsonl').unlink()
  with self.assertRaisesRegex(ValueError,'Missing required source: backing_history.jsonl'):m.analyze(self.p)
  (self.p/'backing_history.jsonl').write_text('{}\n')
  with self.assertRaisesRegex(ValueError,'length differs'):m.analyze(self.p)
if __name__=='__main__':unittest.main()
