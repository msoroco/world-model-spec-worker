import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_adapter import CarlaCrosswalkAdapter, spawn_reviewed_cameras
from crosswalk import SourceError


class API:
    @staticmethod
    def Location(**kw): return Obj(**kw)
    @staticmethod
    def VehicleControl(**kw): return Obj(**kw)
    @staticmethod
    def Rotation(**kw): return Obj(**kw)
    @staticmethod
    def Transform(location, rotation): return Obj(location=location, rotation=rotation)


class Vehicle:
    id = 17
    bounding_box = Obj(get_world_vertices=lambda transform:
                       [Obj(x=x,y=y,z=z) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)] for z in (0,1)])
    def __init__(self): self.controls=[]; self.destroyed=False
    def set_autopilot(self, value): self.autopilot=value
    def get_transform(self): return Obj(location=Obj(x=0,y=0,z=0),rotation=Obj(yaw=0))
    def get_velocity(self): return Obj(x=0,y=0,z=0)
    def apply_control(self, control): self.controls.append(control)
    def destroy(self): self.destroyed=True


class Map:
    name='Town'
    def to_opendrive(self): return '<OpenDRIVE />'
    def get_crosswalks(self): return [Obj(x=x,y=y) for x,y in [(0,0),(2,0),(2,2),(0,2)]]
    def get_waypoint(self, point, project_to_road=False): return Obj(transform=Obj(location=point))


class World:
    def __init__(self): self.map=Map(); self.vehicle=Vehicle(); self.frame=99; self.sensors=[]
    def get_map(self): return self.map
    def get_blueprint_library(self): return Obj(find=lambda name: Obj(id=name))
    def try_spawn_actor(self, bp, transform): return self.vehicle
    def spawn_actor(self, bp, transform):
        sensor=Obj(id=len(self.sensors)+30, type_id='sensor.camera.rgb',
                   attributes=dict(bp.attributes), listen=lambda callback: None,
                   destroy=lambda: None)
        self.sensors.append(sensor)
        return sensor
    def tick(self): self.frame+=1; return self.frame
    def get_snapshot(self): return Obj(frame=self.frame,timestamp=Obj(elapsed_seconds=self.frame*0.05))
    def get_actor(self, actor_id): return None
    def get_environment_objects(self): return []


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.world=World()
        self.adapter=CarlaCrosswalkAdapter(self.world,API,case_id='case')
        self.site={'map_name':'Town','native_opendrive_sha256':hashlib.sha256(b'<OpenDRIVE />').hexdigest(),
                   'frontage_review_sha256':'frontage','highway_review_sha256':'highway',
                   'crosswalk_polygon':[[0,0],[2,0],[2,2],[0,2]],
                   'parking_route':[[-10,0],[0,0]], 'crosswalk_id':'cw', 'marking_status':'marked'}

    def construct(self, destination='on', action='park'):
        self.adapter.verify_crosswalk(self.site)
        actor=self.adapter.spawn_vehicle({'blueprint':'vehicle.sedan'},[-10,0])['actor_id']
        self.adapter.configure_route(actor,self.site['parking_route'],destination,action)
        self.adapter.configure_exception(actor,'none')
        return actor

    def test_native_site_and_controller_calls(self):
        actor=self.construct()
        self.assertEqual(actor,'17')
        self.assertEqual(self.adapter.route[-1],[0,0])
        tick=self.adapter.tick()
        self.assertEqual(tick['frame'],100)
        row=self.adapter.read_subject(actor,100)
        self.assertEqual(row['case_id'],'case')
        self.assertEqual(len(row['body_corners_xy']),4)
        self.assertEqual(row['halt_activity'],'park')
        self.assertFalse(any(row[k] for k in ('traffic_conflict','law_direction','police_direction','device_direction')))
        self.assertTrue(self.world.vehicle.controls[-1].hand_brake)
        self.adapter.brake(actor)
        self.adapter.cleanup()
        self.assertTrue(self.world.vehicle.destroyed)

    def test_off_crosswalk_target_is_upstream(self):
        self.construct(destination='off')
        self.assertEqual(self.adapter.route[-1],[-6,0])

    def test_missing_reviewed_map_rejected(self):
        self.site['native_opendrive_sha256']='wrong'
        with self.assertRaisesRegex(SourceError,'map digest'):
            self.adapter.verify_crosswalk(self.site)

    def test_unsourced_exception_rejected(self):
        actor=self.construct()
        with self.assertRaisesRegex(SourceError,'reviewed exception packet required'):
            self.adapter.configure_exception(actor,'police_direction')

    def test_reviewed_four_camera_spawns(self):
        specs=[]
        poses={}
        for name,(width,height) in __import__('native_capture').CAMERA_SIZES.items():
            specs.append({'name':name,'width':width,'height':height,'fov_deg':90})
            poses[name]={'x':0,'y':0,'z':5,'pitch':-30,'yaw':0,'roll':0}
        self.site['camera_poses']=poses
        self.site['camera_pose_review_sha256']='review'
        old=self.world.get_blueprint_library
        # Make a fresh mutable blueprint per sensor lookup.
        def library():
            def find(name):
                bp=Obj(id=name,attributes={})
                bp.set_attribute=lambda key,value: bp.attributes.__setitem__(key,value)
                return bp
            return Obj(find=find)
        self.world.get_blueprint_library=library
        sensors=spawn_reviewed_cameras(self.world,API,self.site,specs)
        self.assertEqual(len(sensors),4)
        self.assertEqual({v.attributes['image_size_x'] for v in sensors.values()}, {'1920','1280'})
        self.world.get_blueprint_library=old


if __name__=='__main__': unittest.main()
