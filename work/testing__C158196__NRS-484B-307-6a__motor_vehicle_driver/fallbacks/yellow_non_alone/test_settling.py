import unittest,tempfile,pathlib,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import analyze
class TestMeasurement(unittest.TestCase):
 def test_exact_measurement(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)
   rows=[{'frame':i,'time_s':i*.05,'signal_state':state,'ego':{'body_vertices_m':[[x,0,0],[x+1,1,1]]}} for i,(state,x) in enumerate([('Yellow',-20),('Red',-5)])]
   (p/'signal_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   v=analyze.entry_order(p)
   self.assertEqual(len(v['red_at_entry_events']),1)
   self.assertEqual(v['first_red']['frame'],1)
   (p/'signal_history.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source'):analyze.entry_order(p)

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
