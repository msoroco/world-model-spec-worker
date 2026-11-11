import importlib.util,json,subprocess,sys,unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('runner',ROOT/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class Tests(unittest.TestCase):
 def test_cpu_check_and_pinned_four_cameras(self):
  run=subprocess.run([sys.executable,str(ROOT/'runner.py'),'--check'],capture_output=True,text=True)
  self.assertEqual(run.returncode,0,run.stderr)
  self.assertFalse(json.loads(run.stdout)['carla_started'])
  config=json.loads((ROOT/'config.json').read_text())
  self.assertEqual(runner.validate_config(config)['rate_hz'],20)
  config['cameras'].pop()
  with self.assertRaisesRegex(ValueError,'four named cameras'):runner.validate_config(config)
 def test_frame_join_rejects_skipped_sensor_frame(self):
  q=Queue();q.put(NS(frame=8,raw_data=b'x'))
  self.assertEqual(runner.read_sensor(q,8).frame,8)
  q.put(NS(frame=10,raw_data=b'x'))
  with self.assertRaisesRegex(ValueError,'skipped'):runner.read_sensor(q,9)
 def test_camera_transforms_use_native_route_geometry(self):
  def loc(**kwargs):return NS(**kwargs)
  carla=NS(Location=loc,Rotation=lambda **kw:NS(**kw),Transform=lambda p,r:NS(location=p,rotation=r))
  waypoints=[NS(transform=NS(location=loc(x=x,y=0,z=z))) for x,z in ((0,0),(3,1),(6,2))]
  route={'waypoints':waypoints,'crest_waypoint_index':2}
  transforms=runner.camera_transforms(carla,route)
  self.assertEqual(set(transforms),set(runner.CAMERAS))
  self.assertEqual(transforms['overview'].location.z,57)
  self.assertEqual(transforms['driver_reference'].location.z,1.65)
if __name__=='__main__':unittest.main()
