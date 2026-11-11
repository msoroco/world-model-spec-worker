import importlib.util
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('c109749_native_scene',ROOT/'native_scene.py')
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)


def point(x,y):
    return NS(x=x,y=y,z=0.0)


def waypoint(x,y,junction=None):
    return NS(transform=NS(location=point(x,y)),get_junction=lambda:junction)


class Actor:
    def __init__(self,ident,x,y,vx):
        self.id,self.x,self.y,self.vx=ident,x,y,vx
        self.bounding_box=NS(get_world_vertices=lambda transform:[
            point(self.x+dx,self.y+dy) for dx,dy in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    def get_transform(self):return NS(location=point(self.x,self.y))
    def get_velocity(self):return NS(x=self.vx,y=0,z=0)


def selected():
    junction=NS(id=17,bounding_box=NS(location=point(0,0),
             extent=NS(x=5.0,y=4.0),rotation=NS(yaw=0)))
    return {'junction_id':17,
            'ego':{'outside':waypoint(0,-40),'entry':waypoint(0,-4,junction)},
            'oncoming':{'outside':waypoint(40,0),'entry':waypoint(4,0,junction)}}


class NativeSceneTests(unittest.TestCase):
    def test_opposing_waypoint_direction_and_sourced_geometry(self):
        context=scene.junction_context(selected())
        self.assertEqual(context['native_junction_id'],17)
        self.assertEqual(context['oncoming_direction_xy'],[-1.0,0.0])
        self.assertEqual(context['intersection_polygon_xy_m'][0],[-5.0,-4.0])

    def test_measured_initial_yield_and_then_clearance(self):
        chosen=selected();context=scene.junction_context(chosen)
        ego=Actor(10,0,-7,3)
        oncoming=Actor(11,2,0,-3)
        inside=scene.control_inputs(chosen,ego,oncoming,context)
        self.assertTrue(inside['oncoming_in_intersection'])
        self.assertTrue(inside['seen_oncoming_inside'])
        self.assertFalse(inside['oncoming_cleared'])
        oncoming.x=-15
        clear=scene.control_inputs(chosen,ego,oncoming,context,
                                   seen_oncoming_inside=inside['seen_oncoming_inside'])
        self.assertFalse(clear['oncoming_in_intersection'])
        self.assertTrue(clear['oncoming_cleared'])
        self.assertGreater(clear['distance_to_hold_m'],0)

    def test_no_clearance_claim_before_observed_presence(self):
        chosen=selected();context=scene.junction_context(chosen)
        result=scene.control_inputs(chosen,Actor(10,0,-30,3),Actor(11,-15,0,-3),context)
        self.assertFalse(result['oncoming_cleared'])

    def test_degenerate_opposing_approach_rejected(self):
        chosen=selected()
        chosen['oncoming']['entry']=waypoint(40,0,chosen['ego']['entry'].get_junction())
        with self.assertRaisesRegex(ValueError,'approach direction'):
            scene.junction_context(chosen)
