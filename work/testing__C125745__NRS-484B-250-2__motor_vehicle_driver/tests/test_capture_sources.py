import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from capture_sources import CAMERAS, source_cameras, record_sample
from test_median_route_control import scene


class Blueprint:
    def __init__(self):self.attrs={}
    def set_attribute(self,key,value):self.attrs[key]=value

class Sensor:
    def __init__(self):self.stopped=False;self.destroyed=False
    def stop(self):self.stopped=True
    def destroy(self):self.destroyed=True

class World:
    def __init__(self):self.blueprint=Blueprint();self.sensors=[];self.calls=[]
    def get_blueprint_library(self):return NS(find=lambda name:self.blueprint)
    def spawn_actor(self,blueprint,transform,**kwargs):
        sensor=Sensor();self.sensors.append(sensor);self.calls.append((transform,kwargs))
        return sensor

class Actor:
    def __init__(self,actor_id,road):
        self.id=actor_id;self.road=road
        self.pose=NS(location=NS(x=0,y=0),rotation=NS(yaw=0))
        self.bounding_box=NS(get_world_vertices=lambda pose:[NS(x=x,y=y) for x,y in
                             ((0,0),(0,2),(2,2),(2,0))])
    def get_transform(self):return self.pose
    def get_location(self):return self.road

class FrameMap:
    def __init__(self):self.rows=[]
    def append(self,frame,time):
        row={'video_frame':len(self.rows),'carla_frame':frame,'time_s':time}
        self.rows.append(row);return row

class CaptureTests(unittest.TestCase):
    def test_four_named_cameras_spawn_and_cleanup(self):
        world=World();ego=object();transforms={name:name for name in CAMERAS}
        with source_cameras(world,ego,transforms) as sensors:
            self.assertEqual(set(sensors),set(CAMERAS))
            self.assertEqual(world.calls[-1],('driver_reference',{'attach_to':ego}))
            self.assertEqual(world.blueprint.attrs['sensor_tick'],'0.05')
        self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))
        with self.assertRaisesRegex(ValueError,'four named'):
            with source_cameras(world,ego,{'overview':'only'}):pass

    def test_original_body_and_camera_join(self):
        cfg=scene();cfg['intersection_id']=44
        cfg['approaches']['ego']['road_id']=1
        cfg['approaches']['other']['road_id']=2
        world_map=NS(get_waypoint=lambda road,project_to_road=False:
                     NS(road_id=road,lane_id=1,is_junction=False))
        ego,other=Actor(10,1),Actor(11,2)
        snapshot=NS(frame=123,timestamp=NS(elapsed_seconds=6.15))
        frames={name:123 for name in CAMERAS}
        mapping=FrameMap();stream=io.StringIO()
        mapped,row=record_sample(mapping,stream,snapshot,world_map,ego,other,
                                NS(id=17),frames,cfg)
        self.assertEqual(mapped['carla_frame'],123)
        self.assertEqual(row['ego']['body_vertices_xy_m'][0],[0.,0.])
        self.assertEqual(json.loads(stream.getvalue())['other']['actor_id'],11)
        bad=dict(frames);bad['approach']=122
        with self.assertRaisesRegex(ValueError,'camera frames'):
            record_sample(mapping,stream,snapshot,world_map,ego,other,NS(id=17),bad,cfg)
        self.assertEqual(len(mapping.rows),1)

if __name__=='__main__':unittest.main()
