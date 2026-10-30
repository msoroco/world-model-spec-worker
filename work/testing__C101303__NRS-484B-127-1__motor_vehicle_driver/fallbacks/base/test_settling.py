import unittest,tempfile,pathlib,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import analyze
class TestMeasurement(unittest.TestCase):
 def test_exact_measurement(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)
   rows=[{'time_s':i*.05,'ego_speed_mps':10,'lead_speed_mps':9,'along_road_body_gap_m':50-i,'ego_lane_id':-1,'lane_change_requested':False} for i in range(3)]
   (p/'following_samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   v=analyze.following_gap(p)
   self.assertEqual(v['minimum_body_gap_m'],48)
   self.assertEqual(v['time_gap_s_samples'],[5,4.9,4.8])
   (p/'following_samples.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source'):analyze.following_gap(p)

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
