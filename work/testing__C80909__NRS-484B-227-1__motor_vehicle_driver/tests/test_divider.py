import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


measure=load("divider_measurements")
construction=load("barrier_construction")
route=load("left_turn_route")


def body(x,y):return [[x+dx,y+dy] for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1))]


class DividerTests(unittest.TestCase):
    def fixture(self,root,at_opening_x=15):
        ctx={"native_map_id":"TownX","divided_highway_source":"road-and-camera-review",
             "roadway_boundaries_source":"native-map-and-body",
             "opening_geometry_source":"native-divider-gap",
             "barrier_actors_source":"native-world-vertices",
             "other_vehicle_source":"native-actor-and-camera",
             "right_hand_roadway_xy_m":[[0,-10],[30,-10],[30,-2],[0,-2]],
             "destination_roadway_xy_m":[[0,2],[30,2],[30,10],[0,10]],
             "dividing_space_xy_m":[[0,-2],[30,-2],[30,2],[0,2]],
             "opening_xy_m":[[10,-2],[20,-2],[20,2],[10,2]]}
        (root/"divider_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(x,y,heading) in enumerate(((0,-5,[1,0]),(12,-5,[1,0]),(at_opening_x,0,[0.7,.7]),(15,5,[0,1]))):
            rows.append({"frame":100+i,"time_s":1+i*.05,
                         "ego_body_vertices_xy_m":body(x,y),
                         "other_body_vertices_xy_m":body(25,-5),
                         "ego_forward_xy":heading})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"movement_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_complete_body_through_real_opening_and_left_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["starts_on_right_hand_roadway"])
            self.assertTrue(result["opening_traversed_observed"])
            self.assertFalse(result["any_body_overlap_outside_opening"])
            self.assertEqual(result["observed_turn_angle_degrees"],90)
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,at_opening_x=5)
            self.assertTrue(measure.analyze(root)["any_body_overlap_outside_opening"])

    def test_stale_frame_and_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)
            self.fixture(root)
            (root/"movement_history.jsonl").unlink()
            with self.assertRaisesRegex(ValueError,"Missing original source"):measure.analyze(root)

    def test_two_native_barrier_spawns_straddle_opening_and_cleanup(self):
        destroyed=[]
        def actor(xmin,xmax):
            vertices=[NS(x=x,y=y) for x,y in ((xmin,-2),(xmin,2),(xmax,2),(xmax,-2))]
            return NS(bounding_box=NS(get_world_vertices=lambda transform:vertices),
                      get_transform=lambda:"transform",destroy=lambda:destroyed.append(True))
        a,b=actor(0,8),actor(22,30)
        spawned=iter((a,b))
        world=NS(try_spawn_actor=lambda blueprint,transform:next(spawned))
        opening=[[10,-2],[20,-2],[20,2],[10,2]]
        with construction.spawn_barrier_opening(world,[("left","a"),("right","b")],opening,(1,0)) as built:
            self.assertEqual(len(built["actors"]),2)
            self.assertLess(built["section_axis_offsets_m"][0],0)
            self.assertGreater(built["section_axis_offsets_m"][1],0)
        self.assertEqual(destroyed,[True,True])

    def test_blocked_space_comparator_requires_barrier_clearance_and_no_named_opening(self):
        context={"right_hand_roadway_xy_m":[[0,-10],[30,-10],[30,-2],[0,-2]],
                 "destination_roadway_xy_m":[[0,2],[30,2],[30,10],[0,10]],
                 "dividing_space_xy_m":[[0,-2],[30,-2],[30,2],[0,2]],
                 "opening_xy_m":[[10,-2],[20,-2],[20,2],[10,2]]}
        barriers=[[[0,-2],[8,-2],[8,2],[0,2]],
                  [[22,-2],[30,-2],[30,2],[22,2]]]
        receipt=route.validate_blocked_space_route(
            context,[(5,-5),(9,-5),(9,0),(9,5)],barriers,body_radius_m=.4)
        self.assertTrue(receipt['divider_outside_opening_traversed'])
        self.assertEqual(receipt['statutory_opening_judgment'],'unresolved')
        with self.assertRaisesRegex(ValueError,'collides with physical barrier'):
            route.validate_blocked_space_route(
                context,[(5,-5),(7,-5),(7,0),(7,5)],barriers,body_radius_m=.4)
        with self.assertRaisesRegex(ValueError,'enters named opening'):
            route.validate_blocked_space_route(
                context,[(5,-5),(15,-5),(15,0),(15,5)],barriers,body_radius_m=.4)
        straight=route.validate_right_roadway_continuation(
            context,[(5,-5),(15,-5),(25,-5)],body_radius_m=.4)
        self.assertTrue(straight['right_roadway_swept_clearance'])
        with self.assertRaisesRegex(ValueError,'leaves right-hand roadway'):
            route.validate_right_roadway_continuation(
                context,[(5,-5),(15,-5),(15,5)],body_radius_m=.4)

    def test_left_turn_route_has_body_clearance_and_applies_native_control(self):
        from unittest.mock import patch
        import sys
        context={"right_hand_roadway_xy_m":[[0,-10],[30,-10],[30,-2],[0,-2]],
                 "destination_roadway_xy_m":[[0,2],[30,2],[30,10],[0,10]],
                 "dividing_space_xy_m":[[0,-2],[30,-2],[30,2],[0,2]],
                 "opening_xy_m":[[10,-2],[20,-2],[20,2],[10,2]]}
        points=[(5,-5),(15,-5),(15,0),(15,5)]
        receipt=route.validate_route(context,points,body_radius_m=1.0)
        self.assertEqual(receipt['turn_angle_degrees'],90)
        with self.assertRaisesRegex(ValueError,'blocked dividing space'):
            route.validate_route(context,[(5,-5),(5,-3),(5,0),(5,5)],body_radius_m=1.0)
        controls=[]
        state=NS(location=NS(x=5,y=-5),rotation=NS(yaw=0))
        vehicle=NS(get_transform=lambda:state,apply_control=controls.append)
        fake_carla=NS(VehicleControl=lambda **kw:NS(**kw))
        with patch.dict(sys.modules,{'carla':fake_carla}):
            controller=route.WaypointController(points)
            first=controller.step(vehicle)
            self.assertFalse(first['arrived'])
            self.assertGreater(controls[-1].throttle,0)
            state.location.x,state.location.y,state.rotation.yaw=15,-5,0
            controller.step(vehicle)
            state.location.x,state.location.y,state.rotation.yaw=15,0,90
            controller.step(vehicle)
            state.location.x,state.location.y,state.rotation.yaw=15,5,90
            final=controller.step(vehicle)
            self.assertTrue(final['arrived'])
            self.assertEqual(controls[-1].brake,1.0)


if __name__=="__main__":unittest.main()
