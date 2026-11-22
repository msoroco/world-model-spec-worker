import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_driver import apply_ego, body_polygon, control_step, spawn_vehicles


def rectangle(y):
    return [[-.2,y-.2],[.2,y-.2],[.2,y+.2],[-.2,y+.2]]


def scene():
    return {"crossing": {"crossing_id": "A-B-west",
                         "map_source_sha256": hashlib.sha256(b"inspected map").hexdigest(),
                         "bounds_xy_m": [-1,-1,1,1]},
            "ego_highway": "A", "other_highway": "B", "other_entered_first": True,
            "ego_approach_road_id": 10, "other_approach_road_id": 20,
            "ego_route_xy_m": [[-3,0],[0,0],[3,0]],
            "other_route_xy_m": [[0,-3],[0,0],[0,3]]}


class NativeDriverTests(unittest.TestCase):
    def test_next_tick_yield_then_release(self):
        s = scene()
        state = {}
        for frame, other_y, expected in ((0,-2,"brake"),(1,0,"brake"),(2,0,"brake"),(3,2,"proceed")):
            state = control_step(s,state,frame=frame,ego_body=rectangle(-2),
                                 other_body=rectangle(other_y))
            self.assertEqual(state["request"], expected)
        with self.assertRaisesRegex(ValueError, "stale"):
            control_step(s,state,frame=3,ego_body=rectangle(-2),other_body=rectangle(2))

    def test_retreat_from_crossing_does_not_release(self):
        s=scene();state={}
        state=control_step(s,state,frame=0,ego_body=rectangle(-2),other_body=rectangle(-2))
        state=control_step(s,state,frame=1,ego_body=rectangle(-2),other_body=rectangle(0))
        state=control_step(s,state,frame=2,ego_body=rectangle(-2),other_body=rectangle(-2))
        self.assertFalse(state["other_cleared"])
        self.assertEqual(state["request"],"brake")

    def test_advance_request_and_other_later_release_ego(self):
        for first, response in ((True, "advance"), (False, "yield")):
            s=scene();s["other_entered_first"]=first;s["ego_response_request"]=response
            state=control_step(s,{},frame=0,ego_body=rectangle(-2),other_body=rectangle(-2))
            self.assertEqual(state["request"],"proceed")
        s=scene();s["ego_response_request"]="yield"
        state=control_step(s,{},frame=0,ego_body=rectangle(-2),other_body=rectangle(-2))
        self.assertEqual(state["request"],"brake")

    def test_body_projection_and_control_call(self):
        class Point:
            def __init__(self,x,y): self.x,self.y=x,y
        class Box:
            def get_world_vertices(self,transform):
                return [Point(x,y) for z in (0,1) for x,y in
                        ((-.2,-.2),(.2,-.2),(.2,.2),(-.2,.2))]
        class Actor:
            bounding_box=Box()
            def get_transform(self): return object()
            def apply_control(self,control): self.applied=control
        class Carla:
            @staticmethod
            def VehicleControl(**kwargs): return kwargs
        actor=Actor()
        self.assertEqual(len(body_polygon(actor)),4)
        apply_ego(actor,Carla,{"request":"brake"})
        self.assertEqual(actor.applied["brake"],1.0)

    def test_spawn_checks_map_and_cleans_failed_second_actor(self):
        class Waypoint:
            def __init__(self,road,junction,x,y):
                self.road_id=road;self.lane_id=-1;self.is_junction=junction
                self.transform=type("Transform",(),{"location":type("Location",(),{"x":x,"y":y})()})()
                self.following=[]
            def next(self,distance): return self.following
        class Map:
            def __init__(self,disconnect=False):
                self.nodes={(x,y):Waypoint(10 if abs(x)>=abs(y) else 20,x==0 and y==0,x,y)
                            for x,y in ((-3,0),(0,0),(3,0),(0,-3),(0,3))}
                for route in (((-3,0),(0,0),(3,0)),((0,-3),(0,0),(0,3))):
                    for start,end in zip(route,route[1:]):
                        if disconnect and start==(0,-3):continue
                        self.nodes[start].following.append(self.nodes[end])
            def to_opendrive(self): return "inspected map"
            def get_waypoint(self,point,project_to_road=False):
                return self.nodes.get(point)
        class Blueprint:
            def set_attribute(self,key,value): pass
        class Library:
            def filter(self,pattern): return [Blueprint()]
        class Actor:
            def __init__(self,ident): self.id=ident;self.destroyed=False
            def destroy(self): self.destroyed=True
        class World:
            def __init__(self): self.actors=[];self.fail=False;self.mapping=Map()
            def get_map(self): return self.mapping
            def get_blueprint_library(self): return Library()
            def spawn_actor(self,blueprint,pose):
                if self.fail and self.actors: raise RuntimeError("second spawn failed")
                actor=Actor(len(self.actors)+1);self.actors.append(actor);return actor
        class Carla:
            @staticmethod
            def Location(x,y,z): return x,y
        world=World()
        self.assertEqual(set(spawn_vehicles(world,scene(),Carla)),{"ego","other"})
        world=World();world.fail=True
        with self.assertRaisesRegex(RuntimeError,"second spawn"):
            spawn_vehicles(world,scene(),Carla)
        self.assertTrue(world.actors[0].destroyed)
        world=World();world.mapping=Map(disconnect=True)
        with self.assertRaisesRegex(ValueError,"forward Native waypoint connectivity"):
            spawn_vehicles(world,scene(),Carla)
        self.assertEqual(world.actors,[])


if __name__ == "__main__": unittest.main()
