import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c109749_camera_setup',ROOT/'camera_setup.py')
camera=importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


class Sensor:
    def __init__(self):self.stopped=False;self.destroyed=False
    def stop(self):self.stopped=True
    def destroy(self):self.destroyed=True


class World:
    def __init__(self,fail_at=None):self.fail_at=fail_at;self.spawned=[];self.attributes=[]
    def get_blueprint_library(self):return NS(find=lambda name:NS(set_attribute=lambda key,value:self.attributes.append((key,value))))
    def spawn_actor(self,blueprint,transform,**kwargs):
        if len(self.spawned)==self.fail_at:return None
        sensor=Sensor();self.spawned.append((sensor,kwargs));return sensor


class CameraSetupTests(unittest.TestCase):
    def plan(self):return [{'name':name,'width':size[0],'height':size[1],
                           'fov_deg':75 if name in ('approach','reference_corner') else 90}
                          for name,size in camera.PROFILE.items()]

    def test_four_native_sensors_and_reverse_cleanup(self):
        world=World();ego=object();transforms={name:object() for name in camera.PROFILE}
        with camera.source_cameras(world,ego,transforms,self.plan()) as sensors:
            self.assertEqual(set(sensors),set(camera.PROFILE))
            self.assertEqual(world.spawned[3][1],{'attach_to':ego})
            self.assertEqual(world.spawned[0][1],{})
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor,_ in world.spawned))
        self.assertIn(('fov','75'),world.attributes)

    def test_partial_spawn_failure_cleans_created_sensors(self):
        world=World(fail_at=2)
        with self.assertRaisesRegex(ValueError,'camera spawn failed'):
            with camera.source_cameras(world,object(),{name:object() for name in camera.PROFILE},self.plan()):
                pass
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor,_ in world.spawned))
