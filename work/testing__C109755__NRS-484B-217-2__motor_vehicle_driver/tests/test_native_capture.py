import importlib.util
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_capture',ROOT/'native_capture.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


class Point:
    def __init__(self,x,y,z=0):self.x=x;self.y=y;self.z=z


class FakeActor:
    def __init__(self,vertices):
        self.vertices=vertices
        self.bounding_box=self
    def get_transform(self):return None
    def get_world_vertices(self,_):return [Point(*p) for p in self.vertices]


class Marking:
    type='Solid';color='Yellow';lane_change='None'
class Waypoint:
    left_lane_marking=Marking();road_id=1;lane_id=-1
    def __init__(self,loc):self.transform=type('T',(),{'location':loc})();self.successors=[]
    def next(self,_):return self.successors
class Map:
    def __init__(self,shift=0,connected=True,crossing_x=0):
        self.shift=shift
        self.start=Waypoint(Point(-115,-1.75+shift))
        self.crossing_x=crossing_x
        self.approach=Waypoint(Point(crossing_x-3,-1.75+shift))
        self.crossing=Waypoint(Point(crossing_x,1.75+shift))
        self.exit=Waypoint(Point(crossing_x,25+shift))
        if connected:
            self.start.successors=[self.approach]
            self.approach.successors=[self.crossing]
            self.crossing.successors=[self.exit]
    def get_waypoint(self,loc):
        if loc.x < -105:return self.start
        if loc.x < self.crossing_x-1:return self.approach
        if loc.y < 10:return self.crossing
        return self.exit
class Carla:
    Location=Point


class NativeCaptureTests(unittest.TestCase):
    def test_one_factor_traffic_sweep_issues_both_velocity_commands(self):
        import sys
        sys.path.insert(0,str(ROOT))
        try:
            from runner import load_scene
            from traffic_sweep import CHANGES,select
            scene=load_scene()
            baseline,base_policy,_=select(scene,'baseline')
            for variant in CHANGES:
                changed,policy,_=select(scene,variant)
                differences=[key for key in ('oncoming_start_x_m','following_start_x_m',
                    'oncoming_velocity_x_mps','following_velocity_x_mps')
                    if changed[key]!=baseline[key]]
                self.assertEqual(len(differences),0 if variant=='baseline' else 1)
                self.assertIsNone(policy['legal_cutoff'])
            class Actor:
                def set_target_velocity(self,value):self.velocity=value
            class Vector:
                def __init__(self,x,y,z):self.x=x;self.y=y;self.z=z
            actors={'oncoming':Actor(),'following':Actor()}
            commands=native.apply_traffic_policy(actors,
                select(scene,'oncoming_faster')[1],type('C',(),{'Vector3D':Vector}))
            self.assertEqual(commands,{'oncoming':-3.0,'following':2.0})
            self.assertEqual(actors['oncoming'].velocity.x,-3.0)
            self.assertEqual(actors['following'].velocity.x,2.0)
            with self.assertRaisesRegex(ValueError,'undeclared'):
                select(scene,'unsupported')
        finally:sys.path.remove(str(ROOT))

    def test_original_body_envelope_gap_and_contact(self):
        ego=FakeActor([(0,0,0),(2,0,0),(2,2,0),(0,2,0)])
        other=FakeActor([(5,1,0),(7,1,0),(7,3,0),(5,3,0)])
        self.assertEqual(native.body_gap(ego,other),3)
        touching=FakeActor([(2,1,0),(3,1,0),(3,2,0),(2,2,0)])
        self.assertEqual(native.body_gap(ego,touching),0)

    def test_map_placement_rejects_displaced_lanes(self):
        import sys
        sys.path.insert(0,str(ROOT))
        try:
            from runner import load_scene
            scene=load_scene()
            observed=native.check_map(Map(crossing_x=scene['crossing_x_m']),scene,Carla)
            self.assertFalse(observed['zone_extent_verified'])
            self.assertGreater(len(observed['approach_marking_samples']),20)
            self.assertEqual(observed['sample_interval_max_m'],5)
            self.assertTrue(all(s['marking_type']=='Solid' for s in observed['approach_marking_samples']))
            with self.assertRaisesRegex(ValueError,'too far'):
                native.check_map(Map(2,crossing_x=scene['crossing_x_m']),scene,Carla)
            with self.assertRaisesRegex(ValueError,'no connected left-turn waypoint path'):
                native.check_map(Map(connected=False,crossing_x=scene['crossing_x_m']),scene,Carla)
        finally:sys.path.remove(str(ROOT))

    def test_steering_is_bounded(self):
        class Ego:
            def get_transform(self):
                return type('T',(),{'location':Point(-10,-1.75),'rotation':type('R',(),{'yaw':180})()})()
        self.assertTrue(-.7<=native.steering(Ego(),{'crossing_x_m':0,'approach_lane_center_y_m':-1.75,'exit_y_m':25})<=.7)

    def test_partial_spawn_is_destroyed(self):
        import sys
        sys.path.insert(0,str(ROOT))
        try:
            from runner import load_scene, spawn_scene
            class Actor:
                destroyed=False
                def destroy(self):self.destroyed=True
            class Library:
                def filter(self,_):return ['vehicle']
            class World:
                def __init__(self):self.calls=0;self.first=Actor()
                def get_blueprint_library(self):return Library()
                def spawn_actor(self,*_):
                    self.calls+=1
                    if self.calls==2:raise RuntimeError('blocked spawn')
                    return self.first
            world=World()
            with self.assertRaisesRegex(RuntimeError,'blocked spawn'):
                spawn_scene(world,load_scene(),lambda *args:args)
            self.assertTrue(world.first.destroyed)
        finally:sys.path.remove(str(ROOT))


if __name__=='__main__':unittest.main()
