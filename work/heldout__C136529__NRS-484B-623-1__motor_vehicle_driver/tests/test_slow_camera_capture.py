import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

folder=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(folder))
from slow_camera_capture import CAMERAS, SlowCameraCapture

class Blueprint:
    def __init__(self): self.attributes={}
    def set_attribute(self,k,v): self.attributes[k]=v
class Sensor:
    def __init__(self,bp): self.bp=bp;self.callback=None;self.stopped=False
    def listen(self,cb): self.callback=cb
    def stop(self): self.stopped=True
    def destroy(self): pass
class World:
    def __init__(self): self.sensors=[]
    def get_blueprint_library(self): return SimpleNamespace(find=lambda _:Blueprint())
    def spawn_actor(self,bp,transform,attach_to):
        sensor=Sensor(bp); self.sensors.append(sensor); return sensor
class Sink:
    def __init__(self): self.frames=[]
    def write(self,image): self.frames.append(image.frame)
class CameraTest(unittest.TestCase):
    def test_all_named_original_sources_join_exact_frames(self):
        world=World();sinks={n:Sink() for n in CAMERAS}
        carla=SimpleNamespace(Location=lambda *xyz:xyz,Rotation=lambda *pyr:pyr,
                              Transform=lambda loc,rot:(loc,rot))
        capture=SlowCameraCapture(world,carla,object(),sinks)
        try:
            self.assertEqual(len(world.sensors),4)
            for frame in (41,42):
                for sensor,(name,spec) in zip(world.sensors,CAMERAS.items()):
                    width,height=spec[2]
                    self.assertEqual(sensor.bp.attributes['image_size_x'],str(width))
                    sensor.callback(SimpleNamespace(frame=frame,width=width,height=height))
                capture.wait_for_frame(frame,timeout_s=.01)
            self.assertEqual(capture.verify_frames([41,42]),{n:2 for n in CAMERAS})
        finally: capture.close()
        self.assertTrue(all(s.stopped for s in world.sensors))
    def test_missing_source_and_wrong_dimensions_rejected(self):
        world=World();sinks={n:Sink() for n in CAMERAS}
        carla=SimpleNamespace(Location=lambda *xyz:xyz,Rotation=lambda *pyr:pyr,
                              Transform=lambda loc,rot:(loc,rot))
        capture=SlowCameraCapture(world,carla,object(),sinks)
        try:
            name,spec=next(iter(CAMERAS.items()))
            with self.assertRaisesRegex(ValueError,'dimensions changed'):
                world.sensors[0].callback(SimpleNamespace(frame=7,width=1,height=1))
            with self.assertRaisesRegex(ValueError,'callback failed'):
                capture.verify_frames([7])
        finally: capture.close()

if __name__=='__main__': unittest.main()
