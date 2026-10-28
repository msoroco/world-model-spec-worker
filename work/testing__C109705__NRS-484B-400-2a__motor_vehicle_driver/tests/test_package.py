import importlib.util,pathlib,unittest,math
P=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('draft_runner',P/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_offline(self):m.check()
 def test_braking(self):self.assertGreater(m.command((0,0),0,10,[(i,0) for i in range(20)],2)['brake'],0)
 def test_heading_wrap(self):self.assertLess(abs(m.command((0,0),359,2,[(i,0) for i in range(20)],2)['steer']),.1)
 def test_saturation(self):
  c=m.command((0,0),180,0,[(i,0) for i in range(20)],30);self.assertLessEqual(c['throttle'],.65);self.assertLessEqual(abs(c['steer']),.8)
 def test_speed(self):
  class V:x=3;y=4;z=0
  self.assertEqual(m.speed(V()),5)
