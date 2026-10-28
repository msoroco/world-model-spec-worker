import importlib.util,pathlib,unittest,json,math
P=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runner_'+P.name,P/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TestPackage(unittest.TestCase):
 def test_offline(self):m.offline_check()
 def test_brake(self):self.assertGreater(m.control(0,0,0,15,[(x,0) for x in range(100)],3)['brake'],0)
 def test_heading_wrap(self):self.assertEqual(m.heading_error(359,1),2)
 def test_gap_uses_footprints(self):self.assertEqual(m.physical_gap([[0,0],[4,0]],[[20,0],[24,0]],[1,0]),16)
 def test_window_excludes_acceleration(self):
  s=m.summarize([dict(time_s=1,value=100),dict(time_s=16,value=3),dict(time_s=20,value=5)],15,24);self.assertEqual(s['mean'],4);self.assertEqual(s['sample_window_s'],[16,20])
 def test_empty_window_rejected(self):
  with self.assertRaises(ValueError):m.summarize([],15,24)
 def test_canonical_inline(self):
  p=json.loads((P/'construction.json').read_text())
  for f in p['files']:self.assertEqual((P/f['path']).read_text(),f['content'])
 def test_no_target_as_observation(self):
  c=json.loads((P/'config.json').read_text())
  for case in c['cases']:
   for v in case['variable_assignments'].values():
    if v['kind']=='subject_behavior':self.assertIsNone(v['value'])
