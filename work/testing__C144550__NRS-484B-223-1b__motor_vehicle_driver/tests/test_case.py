import json
import unittest
import tempfile
from pathlib import Path
import runner
class CaseTests(unittest.TestCase):
 def test_exact_selected_geometry_and_channels(self):
  runner.check()
  cfg=json.loads(Path('config.json').read_text())
  self.assertEqual(cfg['selected_case_id'],cfg['case']['case_id'])
  self.assertEqual(cfg['law_id'],cfg['case']['target_law_id'])
 def test_route_continuity(self):
  cfg=json.loads(Path('config.json').read_text())
  points=runner.route(cfg)
  self.assertTrue(all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))<=1.5 for a,b in zip(points,points[1:])))

 def test_capture_side_original_frame_writer(self):
  from worker_exchange.native_output import FrameMap
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'map.jsonl'
   with FrameMap(path) as writer:
    runner.append_original_frame(writer,31,.05)
    runner.append_original_frame(writer,32,.10)
   rows=[json.loads(line) for line in path.read_text().splitlines()]
   self.assertEqual([(r['video_frame'],r['carla_frame'],r['native_frame']) for r in rows],[(0,31,31),(1,32,32)])
   with self.assertRaises(FileExistsError):FrameMap(path)

 def test_capture_side_rejects_duplicate_frame(self):
  from worker_exchange.native_output import FrameMap
  with tempfile.TemporaryDirectory() as tmp:
   with FrameMap(Path(tmp)/'map.jsonl') as writer:
    runner.append_original_frame(writer,31,.05)
    with self.assertRaises(ValueError):runner.append_original_frame(writer,31,.10)

 def test_restoration_double_both_world_kinds_and_bad_readback(self):
  from worker_exchange.world_restore import snapshot,restore
  class Values:
   def __init__(self,value):self.value=value
  class Map:
   def __init__(self,name,source):self.name=name;self.source=source
   def to_opendrive(self):return self.source
  class World:
   def __init__(self,name,source):self.map=Map(name,source);self.settings=Values(2);self.weather=Values(3)
   def get_map(self):return self.map
   def get_settings(self):return self.settings
   def get_weather(self):return self.weather
   def apply_settings(self,value):self.settings=value
   def set_weather(self,value):self.weather=value
  class Client:
   def __init__(self,packaged):self.packaged=packaged;self.corrupt=False;self.world=World('Town01' if packaged else 'generated','<original/>')
   def get_world(self):return self.world
   def get_available_maps(self):return ['Town01'] if self.packaged else []
   def load_world(self,name):self.world=World(name,'<wrong/>' if self.corrupt else '<original/>')
   def generate_opendrive_world(self,source):self.world=World('generated','<wrong/>' if self.corrupt else source)
  for packaged in (True,False):
   client=Client(packaged);saved=snapshot(client);client.world=World('changed','<other/>')
   self.assertTrue(restore(client,saved)['restored'])
   client.corrupt=True
   with self.assertRaisesRegex(ValueError,'OpenDRIVE readback'):
    restore(client,saved)

 def test_native_result_missing_fields_and_missing_frame_identity_rejected(self):
  from worker_exchange.native_output import write_result,FrameMap
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaisesRegex(ValueError,'Missing native result field'):write_result(tmp,{'case_id':'diagnostic'})
   with FrameMap(Path(tmp)/'video_frames.jsonl') as writer:
    runner.append_original_frame(writer,9,.05)
   row=json.loads((Path(tmp)/'video_frames.jsonl').read_text())
   self.assertIn('carla_frame',row)
