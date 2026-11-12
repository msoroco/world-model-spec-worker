import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backing_camera import BackingCameraCapture,CAMERAS

class Blueprint:
    def __init__(self):self.attributes={}
    def set_attribute(self,key,value):self.attributes[key]=value
class Sensor:
    def __init__(self):self.callback=None;self.stopped=False
    def listen(self,callback):self.callback=callback
    def stop(self):self.stopped=True
    def destroy(self):pass
class World:
    def __init__(self):self.sensors=[];self.blueprints=[]
    def get_blueprint_library(self):
        world=self
        return SimpleNamespace(find=lambda name:world._blueprint(name))
    def _blueprint(self,name):
        if name!='sensor.camera.rgb':raise ValueError(name)
        b=Blueprint();self.blueprints.append(b);return b
    def spawn_actor(self,blueprint,transform,attach_to):
        s=Sensor();self.sensors.append(s);return s
class Sink:
    def __init__(self):self.frames=[]
    def write(self,image):self.frames.append(image.frame)
    def close(self):pass

class FourViewTests(unittest.TestCase):
    def test_four_named_original_views_and_frame_sync(self):
        world=World();sinks={name:Sink() for name in CAMERAS}
        carla=SimpleNamespace(Location=lambda *args:args,Rotation=lambda *args:args,
            Transform=lambda location,rotation:(location,rotation))
        capture=BackingCameraCapture(world,carla,object(),sinks)
        self.assertEqual(set(CAMERAS),{'overview','approach','reference_corner','driver_reference'})
        self.assertEqual(len(world.sensors),4)
        for sensor,(name,(_,_,size,_)) in zip(world.sensors,CAMERAS.items()):
            image=SimpleNamespace(frame=17,width=size[0],height=size[1],raw_data=b'')
            sensor.callback(image)
        capture.wait_for_frame(17,timeout_s=.01)
        self.assertEqual(capture.verify([17]),{name:1 for name in CAMERAS})
        capture.close();self.assertTrue(all(s.stopped for s in world.sensors))
    def test_missing_view_rejected(self):
        with self.assertRaisesRegex(ValueError,'four named'):
            BackingCameraCapture(World(),object(),object(),{'overview':Sink()})

if __name__=='__main__':unittest.main()
