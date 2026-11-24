"""CPU fake-actor protocol tests; original map and motion remain unverified."""
import importlib.util
import io
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c125745_native", ROOT/"native_crossing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeBox:
    def get_world_vertices(self, transform):
        return [NS(x=transform.location.x+dx,y=transform.location.y+dy,z=z)
                for z in (0,2) for dx,dy in ((-1,-.5),(1,-.5),(1,.5),(-1,.5))]


class FakeActor:
    def __init__(self, ident, x, y):
        self.id=ident;self.is_alive=True;self.location=NS(x=x,y=y)
        self.velocity=NS(x=0,y=0,z=0)
        self.bounding_box=FakeBox();self.last=None
    def get_transform(self):return NS(location=self.location,rotation=NS(yaw=0))
    def get_location(self):return self.location
    def get_velocity(self):return self.velocity
    def apply_control(self, control):self.last=control


class FakeCarla:
    @staticmethod
    def VehicleControl(**kwargs):return kwargs


class NativeTest(unittest.TestCase):
    def setUp(self):
        self.snapshot=NS(frame=100,timestamp=NS(elapsed_seconds=5.0))
        self.actors={"ego":FakeActor(11,-4,0),"other":FakeActor(22,0,-4)}

    def test_capture_two_distinct_original_bodies(self):
        streams={"ego":io.StringIO(),"other":io.StringIO()}
        rows=module.capture_pair(self.snapshot,self.actors,streams)
        self.assertEqual(rows["ego"]["frame"],rows["other"]["frame"])
        self.assertEqual(rows["ego"]["body_vertices_xy_m"],
                         [[-5.0,-.5],[-3.0,-.5],[-3.0,.5],[-5.0,.5]])
        self.assertIn('"actor_id": 22',streams["other"].getvalue())

    def test_duplicate_or_dead_actor_rejected(self):
        self.actors["other"].id=11
        with self.assertRaisesRegex(ValueError,"distinct"):
            module.capture_pair(self.snapshot,self.actors,{"ego":io.StringIO(),"other":io.StringIO()})
        self.actors["other"].id=22;self.actors["other"].is_alive=False
        with self.assertRaisesRegex(ValueError,"dead"):
            module.body_row(self.snapshot,self.actors["other"])

    def test_ego_hold_and_route_follow_are_bounded(self):
        actor=self.actors["ego"]
        self.assertEqual(module.control_step(FakeCarla,actor,[],hold=True),"held")
        self.assertEqual(actor.last["brake"],1.0)
        self.assertEqual(module.control_step(FakeCarla,actor,[(-4,0,0),(-2,0,0),(0,0,0)],hold=False),"released")
        self.assertLessEqual(actor.last["throttle"],.55)
        self.assertEqual(actor.last["steer"],0.0)
        with self.assertRaisesRegex(ValueError,"reviewed route"):
            module.control_step(FakeCarla,actor,[],hold=False)


if __name__=="__main__":unittest.main()
