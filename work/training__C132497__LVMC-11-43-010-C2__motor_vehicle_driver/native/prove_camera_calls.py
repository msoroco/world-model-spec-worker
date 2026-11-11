"""Exercise the real four-camera configuration path without a CARLA server."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('c132497_capture',HERE/'capture.py')
capture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

class Blueprint:
    def __init__(self):self.attributes={}
    def set_attribute(self,key,value):self.attributes[key]=value

class Library:
    def __init__(self):self.lookups=[]
    def find(self,name):
        self.lookups.append(name)
        return Blueprint()

class World:
    def __init__(self):self.library=Library();self.calls=[]
    def get_blueprint_library(self):return self.library
    def spawn_actor(self,bp,transform,attach_to=None):
        actor=object()
        self.calls.append((bp.attributes,transform,attach_to,actor))
        return actor

def location(**kwargs):return SimpleNamespace(**kwargs)
def rotation(**kwargs):return SimpleNamespace(**kwargs)
def transform(loc,rot):return SimpleNamespace(location=loc,rotation=rot)

fake_carla=SimpleNamespace(Location=location,Rotation=rotation,Transform=transform)
ego=object()
for policy,z in (('standard',35),('elevated_overview',42)):
    world=World();owned=[]
    sensors=capture.spawn_camera_sensors(world,fake_carla,ego,policy,owned)
    if (tuple(sensors)!=capture.CAMERA_NAMES or len(owned)!=4 or
            world.library.lookups!=['sensor.camera.rgb']*4):
        raise ValueError('Camera spawn count, identity or blueprint differs')
    expected=((1920,1080,85),(1280,720,90),(1280,720,90),(1280,720,90))
    for i,(attributes,pose,parent,actor) in enumerate(world.calls):
        width,height,fov=expected[i]
        if (attributes!={'image_size_x':str(width),'image_size_y':str(height),
                         'fov':str(fov),'sensor_tick':'0'} or
                parent is not (ego if i==3 else None) or
                sensors[capture.CAMERA_NAMES[i]] is not actor):
            raise ValueError('Camera configuration or attachment differs')
        if pose.location.z!=(z if i==0 else (8,10,1.5)[i-1]):
            raise ValueError('Camera height differs')
    if world.calls[3][1].location.x!=1 or world.calls[3][1].location.y!=0:
        raise ValueError('Driver camera attachment offset differs')

class FailingWorld(World):
    def spawn_actor(self,bp,pose,attach_to=None):return None

try:
    capture.spawn_camera_sensors(FailingWorld(),fake_carla,ego,'standard',[])
except RuntimeError as error:
    if 'source camera spawn failed' not in str(error):raise
else:
    raise ValueError('Failed camera spawn accepted')

print(json.dumps({'passed':True,'camera_configurations':8,
                  'failed_spawn_rejected':True,'native_capture_executed':False}))
