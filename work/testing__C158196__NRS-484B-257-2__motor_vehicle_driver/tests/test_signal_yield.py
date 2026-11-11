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


measure=load("signal_yield_exception")
control=load("signal_control")


def body(x):return [[x+dx,y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]


class SignalTests(unittest.TestCase):
    def fixture(self,root,controls=True,state="Green"):
        ctx={"native_map_id":"TownX","intersection_id":44,"ego_road_id":7,
             "ego_lane_id":-1,"native_signal_id":25,
             "affected_lane_source":"native-affected-waypoints",
             "signal_head_video_source":"front-original",
             "signed_entrance_source":"native-sign-and-camera",
             "junction_source":"native-polygon","sign_inventory_source":"native-signs",
             "other_entrance_source":"native-road","highway_status_source":"review",
             "non_through_highway":True,"ego_entrance_device":"stop",
             "other_entrance_device":"none",
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"signal_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,x in enumerate((0,0,12)):
            rows.append({"frame":100+i,"time_s":1+i*.05,"native_signal_id":25,
                         "ego_road_id":7,"ego_lane_id":-1,"signal_state":state,
                         "signal_controls_ego":controls,"ego_speed_mps":2,
                         "ego_body_vertices_xy_m":body(x),
                         "other_body_vertices_xy_m":body(13)})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_active_governing_signal_at_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["operative_signal_controls_ego_at_entry_observed"])
            self.assertTrue(result["other_inside_at_ego_entry"])
            self.assertEqual(result["subsection_2_applicability"],"signal_control_exception_candidate")
            self.fixture(root,controls=False)
            self.assertFalse(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])
            self.fixture(root,state="Off")
            self.assertFalse(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])

    def test_stale_join_and_wrong_light_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)
            self.fixture(root)
            rows=[json.loads(r) for r in (root/"signal_history.jsonl").read_text().splitlines()]
            rows[2]["native_signal_id"]=999
            (root/"signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"light identity"):measure.analyze(root)

    def test_native_governing_light_selection_and_reversible_state(self):
        class Actors(list):
            def filter(self,pattern):return self
        class Light:
            def __init__(self,road):self.road,self.state=road,"Green"
            def get_affected_lane_waypoints(self):return [NS(road_id=self.road,lane_id=-1)]
            def get_state(self):return self.state
            def set_state(self,value):self.state=value
            def freeze(self,value):self.frozen=value
        selected=Light(7);other=Light(9)
        world=NS(get_actors=lambda:Actors([other,selected]),tick=lambda:None)
        self.assertIs(control.find_governing_signal(world,7,-1),selected)
        with control.SignalControl(world,selected,NS(Red="Red",Green="Green",Off="Off"),"Red"):
            self.assertEqual(selected.state,"Red")
        self.assertEqual(selected.state,"Green")
        self.assertFalse(selected.frozen)


if __name__=="__main__":unittest.main()
