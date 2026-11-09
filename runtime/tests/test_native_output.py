import unittest,tempfile,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from worker_exchange.native_output import frame_record,validate_result,FrameMap,write_result,REQUIRED
class OutputTests(unittest.TestCase):
 def test_identity(self):self.assertEqual(frame_record(0,9,.05),{'video_frame':0,'carla_frame':9,'native_frame':9,'time_s':.05})
 def test_override(self):
  with self.assertRaises(ValueError):frame_record(0,9,.05,carla_frame=8)
 def test_missing(self):
  with self.assertRaises(ValueError):validate_result({})
 def test_invalid_original(self):
  for t in (True,None,float('nan'),float('inf')):
   with self.assertRaises(ValueError):frame_record(0,9,t)
 def test_monotonic_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'mapping.jsonl'
   with FrameMap(p) as m:
    m.append(9,.05)
    with self.assertRaises(ValueError):m.append(9,.1)
    m.append(10,.1)
   self.assertEqual(len(p.read_text().splitlines()),2)
   with self.assertRaises(FileExistsError):FrameMap(p)
 def test_unknown_outcome_preserved(self):
  result={k:{} for k in REQUIRED};result.update(setup_confirmed=False,behavior_attempted=True,maneuver_completed=False,video_references=['raw.mkv'],target_checks=[{'target':'speed','requested':5,'measured':2,'method':'telemetry','tolerance':.1,'matched':False,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}])
  with tempfile.TemporaryDirectory() as tmp:
   p=write_result(tmp,result);self.assertFalse(json.loads(p.read_text())['setup_confirmed'])
   with self.assertRaises(ValueError):write_result(tmp,result)
 def test_nonfinite_measurement(self):
  result={k:{} for k in REQUIRED};result.update(target_checks=[dict(target='x',requested=1,measured=float('nan'),method='source',tolerance=1,matched=False,physical_cause_confirmed=False,cause_evidence='source')],video_references=['raw'])
  with self.assertRaises(ValueError):validate_result(result)
