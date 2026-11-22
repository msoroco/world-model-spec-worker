from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_driver import command_next_tick, original_sample, spawn_vehicle
from test_uturn_control import scene


class NativeDriverTests(unittest.TestCase):
    def test_exact_vehicle_blueprint_binding(self):
        class Map:
            def to_opendrive(self): return "inspected map"
            def get_waypoint(self, point, project_to_road=False):
                return type("Waypoint",(),{"road_id":10 if point["y"]<0 else 20,
                                            "transform":"pose"})()
        class Blueprint:
            def set_attribute(self, key, value): pass
        class Library:
            def __init__(self): self.requested=[]
            def find(self, ident): self.requested.append(ident);return Blueprint()
            def filter(self, pattern): raise AssertionError("unbound vehicle selection")
        class World:
            def __init__(self): self.library=Library()
            def get_map(self): return Map()
            def get_blueprint_library(self): return self.library
            def spawn_actor(self, blueprint, pose): return object()
        world=World()
        selected=scene(); selected["vehicle_blueprint_id"]="vehicle.tesla.model3"
        carla=type("Carla",(),{"Location":staticmethod(lambda **kwargs:kwargs)})
        self.assertIsNotNone(spawn_vehicle(world,selected,carla))
        self.assertEqual(world.library.requested,["vehicle.tesla.model3"])

    def test_spawn_original_body_and_next_tick_command(self):
        class Waypoint:
            def __init__(self, road): self.road_id=road;self.transform=(road,"pose")
        class Map:
            def to_opendrive(self): return "inspected map"
            def get_waypoint(self, point, project_to_road=False):
                return Waypoint(10 if point["y"]<0 else 20)
        class Blueprint:
            def set_attribute(self,key,value): self.role=(key,value)
        class Library:
            def filter(self,pattern): return [Blueprint()]
        class Box:
            def get_world_vertices(self,transform):
                return [type("P",(),{"x":x,"y":y})() for _ in (0,1)
                        for x,y in ((-.2,-.2),(.2,-.2),(.2,.2),(-.2,.2))]
        class Actor:
            id=31;bounding_box=Box()
            def get_transform(self):
                return type("Pose",(),{"location":type("Loc",(),{"x":-3,"y":-2})(),
                                       "rotation":type("Rot",(),{"yaw":0})()})()
            def get_velocity(self): return type("Vel",(),{"x":1,"y":0})()
            def apply_control(self,value): self.control=value
        class World:
            def __init__(self): self.pose=None
            def get_map(self): return Map()
            def get_blueprint_library(self): return Library()
            def spawn_actor(self,bp,pose): self.pose=pose;return Actor()
        class Carla:
            @staticmethod
            def Location(**kwargs): return kwargs
            @staticmethod
            def VehicleControl(**kwargs): return kwargs
        world=World();actor=spawn_vehicle(world,scene(),Carla)
        self.assertEqual(world.pose,(10,"pose"))
        snapshot=type("Snapshot",(),{"frame":10,
            "timestamp":type("Stamp",(),{"elapsed_seconds":.5})()})()
        sample=original_sample(actor,snapshot)
        self.assertEqual(len(sample["body_vertices_xy_m"]),4)
        self.assertEqual(sample["actor_id"],31)
        request=command_next_tick(actor,Carla,scene(),{},sample)
        self.assertEqual(request["request"],"drive")
        self.assertGreater(actor.control["throttle"],0)


if __name__ == "__main__": unittest.main()
