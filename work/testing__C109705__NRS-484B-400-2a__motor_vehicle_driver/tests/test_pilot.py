import json
import unittest
import tempfile
from pathlib import Path
import runner
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore
class PilotTests(unittest.TestCase):
 def test_route_is_continuous_and_within_road(self):
  runner.check()
  for lateral in (1.75,5.25):
   points=runner.route(lateral)
   self.assertTrue(all(abs(x1-x0)<=1.5 and abs(y1-y0)<=1.5 for (x0,y0),(x1,y1) in zip(points,points[1:])))

 def test_actual_capture_side_frame_writer(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'video_frames.jsonl'
   with FrameMap(path) as writer:
    runner.append_original_frame(writer,41,.05,{'view0':{'width':1920,'height':1080}})
    runner.append_original_frame(writer,42,.10,{'view0':{'width':1920,'height':1080}})
   rows=[json.loads(line) for line in path.read_text().splitlines()]
   self.assertEqual([(r['video_frame'],r['carla_frame'],r['native_frame']) for r in rows],[(0,41,41),(1,42,42)])
   with self.assertRaises(FileExistsError):FrameMap(path)

 def test_capture_side_frame_writer_rejects_duplicate(self):
  with tempfile.TemporaryDirectory() as tmp:
   with FrameMap(Path(tmp)/'map.jsonl') as writer:
    runner.append_original_frame(writer,41,.05,{})
    with self.assertRaises(ValueError):runner.append_original_frame(writer,41,.10,{})

 def test_packaged_and_generated_world_restoration(self):
  class Values:
   def __init__(self,value):self.value=value
  class Map:
   def __init__(self,name,source):self.name=name;self.source=source
   def to_opendrive(self):return self.source
  class World:
   def __init__(self,name,source):self.map=Map(name,source);self.settings=Values(7);self.weather=Values(3)
   def get_map(self):return self.map
   def get_settings(self):return self.settings
   def get_weather(self):return self.weather
   def apply_settings(self,x):self.settings=x
   def set_weather(self,x):self.weather=x
  class Client:
   def __init__(self,name,packaged):self.world=World(name,'<OpenDRIVE/>');self.packaged=packaged
   def get_world(self):return self.world
   def get_available_maps(self):return [self.world.map.name] if self.packaged else []
   def load_world(self,name):self.world=World(name,'<OpenDRIVE/>')
   def generate_opendrive_world(self,source):self.world=World('generated',source)
  for packaged in (True,False):
   client=Client('Town01' if packaged else 'generated',packaged)
   saved=snapshot(client)
   client.world=World('changed','<Other/>')
   receipt=restore(client,saved)
   self.assertTrue(receipt['restored'])
   self.assertEqual(client.get_world().get_map().to_opendrive(),'<OpenDRIVE/>')

 def test_failed_restoration_readback_is_detected(self):
  class Broken:
   def get_world(self):return self.world
   def get_available_maps(self):return ['Town01']
   def load_world(self,name):self.world.map.name=name
  class Map:
   name='Town01'
   def to_opendrive(self):return '<wrong/>'
  class World:
   map=Map()
   def get_map(self):return self.map
   def get_settings(self):return object()
   def get_weather(self):return object()
   def apply_settings(self,x):pass
   def set_weather(self,x):pass
  client=Broken();client.world=World()
  with self.assertRaisesRegex(ValueError,'OpenDRIVE readback'):
   restore(client,{'packaged':'Town01','opendrive':'<expected/>','settings':object(),'weather':object()})
