"""Exercise real construction calls through a minimal CARLA-shaped fake."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from native_construction import candidate_opendrive,occluder_probes,spawn_scene,validate_scene
from runner import check_scene
from standing_geometry import measure


class Blueprint:
    def __init__(self,name):self.id=name;self.attributes={}
    def has_attribute(self,key):return key=="role_name"
    def set_attribute(self,key,value):self.attributes[key]=value


class Library:
    def __init__(self):self.requests=[]
    def find(self,name):
        self.requests.append(name)
        return Blueprint(name) if name in ("vehicle.tesla.model3","static.prop.streetbarrier") else None


class Actor:
    def __init__(self,bp,transform,identifier):
        self.bp=bp;self.transform=transform;self.id=identifier;self.controls=[];self.physics=[]
        self.destroyed=False
        self.bounding_box=self
    def get_transform(self):return self.transform
    def get_world_vertices(self,transform):
        x=transform.location.x;y=transform.location.y
        half_x=1. if self.bp.id.startswith("static") else 2.5
        half_y=.4 if self.bp.id.startswith("static") else 1.
        return [SimpleNamespace(x=x+dx*half_x,y=y+dy*half_y,z=z)
                for dx in (-1,1) for dy in (-1,1) for z in (0,2)]
    def set_simulate_physics(self,value):self.physics.append(value)
    def apply_control(self,value):self.controls.append(value)
    def destroy(self):self.destroyed=True


class World:
    def __init__(self):self.library=Library();self.actors=[]
    def get_blueprint_library(self):return self.library
    def spawn_actor(self,bp,transform):
        actor=Actor(bp,transform,len(self.actors)+1);self.actors.append(actor);return actor


class Carla:
    @staticmethod
    def Location(**kwargs):return SimpleNamespace(**kwargs)
    @staticmethod
    def Rotation(**kwargs):return SimpleNamespace(**kwargs)
    @staticmethod
    def Transform(location,rotation):return SimpleNamespace(location=location,rotation=rotation)
    @staticmethod
    def VehicleControl(**kwargs):return SimpleNamespace(**kwargs)


class NativeConstructionTests(unittest.TestCase):
    def scene(self,suffix):
        path=HERE/"cases"/suffix/"scene.json"
        return check_scene(path)[0]

    def test_all_three_source_bound_native_scenes(self):
        for suffix in ("passage_clear_view","passage_blocked","view_occluded_both"):
            scene=self.scene(suffix)
            self.assertEqual(validate_scene(scene,HERE/"candidate-standing-road.xodr"),suffix)
        source=candidate_opendrive()
        self.assertIn('a="2.5"',source)
        self.assertIn('a="3.5"',source)
        self.assertIn('length="160"',source)

    def test_actor_creation_and_both_physical_occluders(self):
        scene=self.scene("view_occluded_both")
        world=World()
        standing,passing,props,actors=spawn_scene(world,scene,Carla)
        self.assertEqual(len(actors),4)
        self.assertEqual(len(props),2)
        self.assertEqual(world.library.requests.count("static.prop.streetbarrier"),2)
        self.assertEqual(standing.physics,[False])
        self.assertTrue(standing.controls[0].hand_brake)
        self.assertEqual(passing.transform.location.x,65)
        probes=occluder_probes(scene,props)["probes"]
        self.assertFalse(probes["negative_x:60.960m"]["clear_geometry"])
        self.assertFalse(probes["positive_x:60.960m"]["clear_geometry"])

    def test_clear_and_blocked_cases_create_no_occluders(self):
        for suffix in ("passage_clear_view","passage_blocked"):
            scene=self.scene(suffix);world=World()
            _,_,props,actors=spawn_scene(world,scene,Carla)
            self.assertEqual(len(actors),2);self.assertEqual(props,[])
            self.assertTrue(all(p["clear_geometry"] for p in occluder_probes(scene,props)["probes"].values()))

    def test_missing_source_and_missing_prop_rejected(self):
        scene=self.scene("view_occluded_both")
        scene["occluder_blueprint_id"]=None
        with self.assertRaises(ValueError):validate_scene(scene)
        scene=self.scene("passage_clear_view")
        scene["map_source_sha256"]="0"*64
        with self.assertRaises(ValueError):validate_scene(scene,HERE/"candidate-standing-road.xodr")

    def test_fallbacks_preserve_case_and_physical_contrast(self):
        expected={"passage_clear_view":(True,True),"passage_blocked":(False,True),
                  "view_occluded_both":(True,False)}
        for suffix,(passage,negative_view) in expected.items():
            primary=self.scene(suffix)
            fallback=check_scene(HERE/"cases"/suffix/"fallback1-scene.json")[0]
            self.assertEqual(primary["case_id"],fallback["case_id"])
            self.assertEqual(primary["map_source_sha256"],fallback["map_source_sha256"])
            self.assertEqual(primary["other_vehicle_centers_xy_m"],fallback["other_vehicle_centers_xy_m"])
            measured=measure(fallback)
            self.assertEqual(measured["physical_passage_observed"],passage)
            self.assertEqual(measured["sight_probes"]["negative_x:60.960m"]["visible"],negative_view)


if __name__=="__main__":unittest.main()
