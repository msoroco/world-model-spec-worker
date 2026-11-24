import unittest,sys
from pathlib import Path
from types import SimpleNamespace as N
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from worker_exchange.world_restore import snapshot,restore
class World:
 def __init__(self,name='OpenDriveMap',xodr='source'):self.name=name;self.xodr=xodr;self.settings=N(synchronous_mode=False,fixed_delta_seconds=None);self.weather=N(cloudiness=1.)
 def get_map(self):return N(name=self.name,to_opendrive=lambda:self.xodr)
 def get_settings(self):return self.settings
 def get_weather(self):return self.weather
 def apply_settings(self,value):self.settings=value
 def set_weather(self,value):self.weather=value
class Client:
 def __init__(self,name='OpenDriveMap'):self.world=World(name);self.calls=[]
 def get_world(self):return self.world
 def get_available_maps(self):return ['Town01']
 def load_world(self,name):self.calls.append(('load',name));self.world=World(name)
 def generate_opendrive_world(self,x):self.calls.append(('generate',x));self.world=World(xodr=x)
class RestoreTests(unittest.TestCase):
 def test_generated(self):
  c=Client();saved=snapshot(c);c.world=World(xodr='changed');self.assertTrue(restore(c,saved)['restored']);self.assertEqual(c.calls,[('generate','source')])
 def test_packaged(self):
  c=Client('Town01');saved=snapshot(c);restore(c,saved);self.assertEqual(c.calls,[('load','Town01')])
 def test_wrong_geometry_rejected(self):
  c=Client();saved=snapshot(c);c.generate_opendrive_world=lambda x:None;c.world=World(xodr='changed')
  with self.assertRaisesRegex(ValueError,'OpenDRIVE'):restore(c,saved)
 def test_wrong_settings_rejected(self):
  c=Client();saved=snapshot(c)
  def generate(x):
   c.world=World();c.world.apply_settings=lambda value:None;c.world.settings=N(synchronous_mode=True)
  c.generate_opendrive_world=generate
  with self.assertRaisesRegex(ValueError,'settings'):restore(c,saved)
