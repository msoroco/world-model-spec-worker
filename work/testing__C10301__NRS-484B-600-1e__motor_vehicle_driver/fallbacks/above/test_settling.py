import unittest,tempfile,pathlib,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import analyze
class TestMeasurement(unittest.TestCase):
 def test_exact_measurement(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)
   for mph in (79,80,81):
    (p/'speed_samples.jsonl').write_text(json.dumps({'frame':1,'time_s':.05,'position_m':[300,0,0],'speed_mps':mph*.44704})+'\n')
    v=analyze.speed_history(p)
    self.assertAlmostEqual(v['max_sampled_mph'],mph)
    self.assertEqual(bool(v['above_80_mph_original_frames']),mph>80)
   (p/'speed_samples.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source: speed_samples.jsonl'):analyze.speed_history(p)

 def test_access_aisle_geometry(self):
  import access_aisle,runner,xml.etree.ElementTree as ET
  tree=ET.parse(runner.ROOT/'scene.xodr')
  self.assertEqual(tree.find("road[@id='1']/lanes/laneSection[@s='400']/right/lane[@id='-2']/width").get('a'),'4')
  self.assertGreater(len(access_aisle.positions()),150)
  self.assertTrue(all(399<=x<=421 and 5<=y<=7.5 for x,y in access_aisle.positions()))

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
