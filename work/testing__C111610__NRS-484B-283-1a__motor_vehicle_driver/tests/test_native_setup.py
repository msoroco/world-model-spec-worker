import importlib.util
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for name in ('crosswalk','native_setup'):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
import native_setup as m


class Point:
    def __init__(self,x,y,z=0): self.x,self.y,self.z=x,y,z
class Transform:
    def __init__(self,location,rotation=None): self.location,self.rotation=location,rotation
class Rotation:
    def __init__(self,yaw=0): self.yaw=yaw
class Waypoint:
    road_id=1
    lane_id=1
    def __init__(self,point): self.transform=Transform(Point(*point))
    def next(self,step): return [Waypoint((self.transform.location.x+step,self.transform.location.y))]
class Map:
    def get_waypoint(self,location): return Waypoint((location.x,location.y))
class Actor:
    def __init__(self,id): self.id=id; self.destroyed=False
    def destroy(self): self.destroyed=True
class Library:
    def find(self,name): return name if name in ('vehicle.test','walker.test') else None
class World:
    def __init__(self,fail=False): self.actors=[]; self.fail=fail
    def get_map(self): return Map()
    def get_blueprint_library(self): return Library()
    def spawn_actor(self,bp,transform):
        if self.fail and self.actors: return None
        actor=Actor(len(self.actors)+1); self.actors.append(actor); return actor


class NativeTest(unittest.TestCase):
    def scene(self):
        return {'case_id':'destination_occupied','turn_direction':'left',
                'pedestrian_half':'destination','ego_blueprint_id':'vehicle.test',
                'pedestrian_blueprint_id':'walker.test','ego_start_xy_m':[0,0],
                'pedestrian_start_xy_m':[4,1], 'ego_yaw_deg':0,
                'pedestrian_yaw_deg':90,'engineering_throttle':0.2}
    def site(self):
        return {'turn_route':[[0,0],[2,0],[4,0]],
                'destination_half':[[[2,0],[6,0],[6,4],[2,4]]]}
    def test_native_creation_and_identity(self):
        carla=types.SimpleNamespace(Location=Point,Transform=Transform,Rotation=Rotation)
        world=World()
        built=m.construct(world,carla,self.scene(),self.site())
        self.assertEqual((built['ego'].id,built['pedestrian'].id),(1,2))
        self.assertEqual(len(built['route_waypoint_ids']),3)
    def test_native_spawn_failure_cleans_ego(self):
        carla=types.SimpleNamespace(Location=Point,Transform=Transform,Rotation=Rotation)
        world=World(fail=True)
        with self.assertRaisesRegex(m.ConstructionError,'spawn failed'):
            m.construct(world,carla,self.scene(),self.site())
        self.assertTrue(world.actors[0].destroyed)
    def test_wrong_half_rejected(self):
        carla=types.SimpleNamespace(Location=Point,Transform=Transform,Rotation=Rotation)
        scene=self.scene(); scene['pedestrian_start_xy_m']=[10,1]
        with self.assertRaisesRegex(m.ConstructionError,'wrong directional half'):
            m.construct(World(),carla,scene,self.site())
    def test_controller_source_and_occupancy(self):
        scene=self.scene()
        measured={'source_frame':20,'source_refs':['native/motion.jsonl'],
                  'device_condition':'absent','pedestrian_in_crosswalk':True,
                  'pedestrian_on_destination_half':True}
        self.assertEqual(m.control_policy(scene,measured)['brake'],1.0)
        measured['pedestrian_on_destination_half']=False
        self.assertEqual(m.control_policy(scene,measured)['brake'],0.0)
        measured['device_condition']='operating'
        self.assertEqual(m.control_policy(scene,measured)['brake'],1.0)
        measured['source_refs']=[]
        with self.assertRaisesRegex(m.ConstructionError,'measurement missing'):
            m.control_policy(scene,measured)

if __name__ == '__main__': unittest.main()
