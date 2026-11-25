import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('camera_setup',ROOT/'camera_setup.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


class CamerasTests(unittest.TestCase):
    def test_four_original_sensors_spawn_and_cleanup(self):
        seen=[]
        class Blueprint:
            def set_attribute(self,key,value):seen.append((key,value))
        class Sensor:
            def __init__(self,name):self.name=name
            def stop(self):seen.append(('stop',self.name))
            def destroy(self):seen.append(('destroy',self.name))
        world=NS(get_blueprint_library=lambda:NS(find=lambda name:Blueprint()),
                 spawn_actor=lambda blueprint,transform,**kwargs:Sensor(transform))
        plan=[{'name':name,'width':size[0],'height':size[1],'fov_deg':90}
              for name,size in MODULE.PROFILE.items()]
        transforms={name:name for name in MODULE.PROFILE}
        with MODULE.source_cameras(world,object(),transforms,plan) as sensors:
            self.assertEqual(set(sensors),set(MODULE.PROFILE))
        self.assertEqual(sum(key=='destroy' for key,value in seen),4)
        self.assertIn(('sensor_tick','0.05'),seen)

    def test_missing_fourth_camera_rejected(self):
        world=NS()
        names=list(MODULE.PROFILE)
        plan=[{'name':name,'width':MODULE.PROFILE[name][0],
               'height':MODULE.PROFILE[name][1],'fov_deg':90} for name in names[:-1]]
        with self.assertRaisesRegex(ValueError,'four named'):
            with MODULE.source_cameras(world,object(),dict.fromkeys(names),plan):pass


if __name__=='__main__':unittest.main()
