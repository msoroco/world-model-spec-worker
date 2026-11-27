import sys
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from divider_construction import spawn_divider, validate_divider, verify_recorded_divider
from test_uturn_control import scene as base_scene


def scene():
    item=base_scene()
    item["divider_props"]=[{"blueprint_id":"static.prop.barrier",
        "bounds_xy_m":rect,"z_m":0}
        for rect in item["context"]["closed_divider_bounds_xy_m"]]
    return item


class DividerTests(unittest.TestCase):
    def test_static_geometry_and_native_spawn(self):
        item=scene()
        self.assertEqual(len(validate_divider(item)),2)
        class Actor:
            def __init__(self,rect): self.rect=rect;self.bounding_box=self;self.destroyed=False
            def get_transform(self): return None
            def get_world_vertices(self,transform):
                x0,y0,x1,y1=self.rect
                return [types.SimpleNamespace(x=x,y=y) for _ in (0,1)
                        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
            def destroy(self): self.destroyed=True
        class World:
            def __init__(self): self.actors=[];self.bad=False
            def get_blueprint_library(self): return self
            def find(self,ident):
                if ident!="static.prop.barrier": raise AssertionError(ident)
                return ident
            def spawn_actor(self,blueprint,transform):
                rect=item["divider_props"][len(self.actors)]["bounds_xy_m"]
                if self.bad: rect=[rect[0],rect[1],rect[2]-.5,rect[3]]
                actor=Actor(rect);self.actors.append(actor);return actor
        carla=types.SimpleNamespace(Location=lambda **k:k,Rotation=lambda **k:k,
            Transform=lambda location,rotation:(location,rotation))
        world=World()
        self.assertEqual(len(spawn_divider(world,item,carla)),2)
        self.assertFalse(any(actor.destroyed for actor in world.actors))
        bad=World();bad.bad=True
        with self.assertRaisesRegex(ValueError,"footprint differs"):
            spawn_divider(bad,item,carla)
        self.assertTrue(all(actor.destroyed for actor in bad.actors))
        geometry={"actors":[{"actor_id":ident,"blueprint_id":"static.prop.barrier",
            "body_vertices_xy_m":[[rect[0],rect[1]],[rect[2],rect[1]],
                                   [rect[2],rect[3]],[rect[0],rect[3]]]}
            for ident,rect in zip((31,32),item["context"]["closed_divider_bounds_xy_m"])]}
        context={**item["context"],"divider_actor_ids":[31,32]}
        self.assertTrue(verify_recorded_divider(context,item["divider_props"],geometry)
                        ["closed_divider_coverage_verified"])
        geometry["actors"][0]["body_vertices_xy_m"][1][0] -= .5
        with self.assertRaisesRegex(ValueError,"footprint differs"):
            verify_recorded_divider(context,item["divider_props"],geometry)

    def test_rejects_unconstructed_gap_and_opening_prop(self):
        item=scene()
        item["divider_props"].pop()
        with self.assertRaisesRegex(ValueError,"unconstructed gap"):
            validate_divider(item)
        item=scene()
        item["divider_props"][0]["bounds_xy_m"]=[-.5,-.5,.5,.5]
        with self.assertRaisesRegex(ValueError,"extends into opening"):
            validate_divider(item)


if __name__=="__main__": unittest.main()
