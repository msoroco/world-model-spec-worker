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


measure=load("crosswalk_stop_measurements")
sign=load("stop_sign_control")


def body(x):return [[x+dx,y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]


class CrosswalkTests(unittest.TestCase):
    def fixture(self,root,stop_x=5,origin="marked"):
        ctx={"native_map_id":"TownX","intersection_id":44,"approach_road_id":7,
             "approach_lane_id":-1,"native_stop_sign_id":25,
             "sign_governance_source":"native-trigger-and-original-camera",
             "crosswalk_source":"marking-and-sidewalk-review",
             "crosswalk_nearside_source":"native-route-order",
             "junction_source":"native-polygon",
             "near_side_crosswalk_exists":True,"crosswalk_origin":origin,
             "stop_line_exists":True,"approach_forward_xy":[1,0],
             "crosswalk_polygon_xy_m":[[10,-5],[12,-5],[12,5],[10,5]],
             "intersection_polygon_xy_m":[[20,-5],[30,-5],[30,5],[20,5]]}
        (root/"approach_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(x,speed) in enumerate(((0,4),(stop_x,0),(11,2),(22,3))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"road_id":7,"lane_id":-1,
                         "stop_sign_id":25,"ego_speed_mps":speed,"ego_body_vertices_xy_m":body(x)})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"stop_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_crosswalk_precedes_stop_line_even_when_unmarked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertEqual(result["selected_reference"],"near_side_crosswalk")
            self.assertTrue(result["stop_line_present_but_lower_priority"])
            self.assertTrue(result["full_halt_before_crosswalk_and_junction_observed"])
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,origin="sidewalk_connection")
            self.assertTrue(measure.analyze(root)["full_halt_before_crosswalk_and_junction_observed"])
            self.fixture(root,stop_x=11)
            self.assertFalse(measure.analyze(root)["full_halt_before_crosswalk_and_junction_observed"])

    def test_missing_crosswalk_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/"approach_context.json").read_text())
            ctx["near_side_crosswalk_exists"]=False
            (root/"approach_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"crosswalk absent"):measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)

    def test_native_stop_sign_trigger_governs_approach(self):
        class Actors(list):
            def filter(self,pattern):return self
        chosen=NS(trigger_volume=NS(contains=lambda p,t:True),get_transform=lambda:"chosen")
        wrong=NS(trigger_volume=NS(contains=lambda p,t:False),get_transform=lambda:"wrong")
        world=NS(get_actors=lambda:Actors([wrong,chosen]))
        approach=NS(transform=NS(location="ego-approach"))
        self.assertIs(sign.find_governing_stop_sign(world,approach),chosen)
        with self.assertRaisesRegex(ValueError,"found 0"):
            sign.find_governing_stop_sign(NS(get_actors=lambda:Actors([wrong])),approach)


if __name__=="__main__":unittest.main()
