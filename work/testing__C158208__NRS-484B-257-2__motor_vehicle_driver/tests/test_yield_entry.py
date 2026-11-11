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


measure=load("yield_entry_measurements")
control=load("yield_sign_control")


def body(x):return [[x+dx,y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]


class YieldEntryTests(unittest.TestCase):
    def fixture(self,root,other_device="none"):
        ctx={"native_map_id":"TownX","intersection_id":44,"ego_approach_road_id":7,
             "other_approach_road_id":9,"native_yield_sign_id":25,
             "sign_governance_source":"Native-trigger-and-camera",
             "entrance_inventory_source":"all-entrance-map-and-camera",
             "yield_reference_source":"native-line-or-view","highway_status_source":"road-review",
             "non_through_highway":True,"police_control":False,"traffic_signal_control":False,
             "ego_entrance_device":"yield",
             "entrances":[{"road_id":7,"device":"yield"},{"road_id":9,"device":other_device}],
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"intersection_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(ego_x,other_x,speed) in enumerate(((0,0,4),(0,0,2),(12,12,1))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"ego_road_id":7,
                         "yield_sign_id":25,"ego_speed_mps":speed,
                         "ego_body_before_yield_reference":i<2,
                         "ego_body_vertices_xy_m":body(ego_x),
                         "other_body_vertices_xy_m":body(other_x)})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"entry_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_yield_response_and_other_entrance_obligation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["observed_slowed_or_stopped_before_reference"])
            self.assertTrue(result["other_not_obligated_by_stop_or_yield"])
            self.assertTrue(result["other_inside_at_ego_entry"])
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,"stop")
            self.assertFalse(measure.analyze(root)["other_not_obligated_by_stop_or_yield"])

    def test_signal_exception_and_stale_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/"intersection_context.json").read_text())
            ctx["traffic_signal_control"]=True
            (root/"intersection_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"exception"):measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)

    def test_native_yield_trigger_selects_ego_approach(self):
        class Actors(list):
            def filter(self,pattern):return self
        chosen=NS(trigger_volume=NS(contains=lambda p,t:True),get_transform=lambda:"a")
        wrong=NS(trigger_volume=NS(contains=lambda p,t:False),get_transform=lambda:"b")
        world=NS(get_actors=lambda:Actors([wrong,chosen]))
        waypoint=NS(transform=NS(location="ego-approach"))
        self.assertIs(control.find_governing_yield_sign(world,waypoint),chosen)
        with self.assertRaisesRegex(ValueError,"found 0"):
            control.find_governing_yield_sign(NS(get_actors=lambda:Actors([wrong])),waypoint)


if __name__=="__main__":unittest.main()
