import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


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
             "entrance_road_ids":[7,9,11],
             "entrances":[{"road_id":7,"device":"yield"},{"road_id":9,"device":other_device},
                          {"road_id":11,"device":"none"}],
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"intersection_context.json").write_text(json.dumps(ctx))
        cameras={}
        for name in ("overview","approach","reference_corner","driver_reference"):
            path=root/(name+".mkv")
            path.write_text("diagnostic camera source "+name)
            cameras[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        (root/"site_review.json").write_text(json.dumps({
            "intersection_context_sha256":hashlib.sha256((root/"intersection_context.json").read_bytes()).hexdigest(),
            "native_yield_sign_id":25,"sign_face_observed":"yield",
            "proper_sign_judgment":"unresolved","marked_stop_line_observed":True,
            "near_crosswalk_observed":True,"nearest_view_point_xy_m":[9,0],
            "camera_sha256":cameras,
            "reviewed_carla_frames":[100,101,102],"reviewed_frame_count":3}))
        rows=[]
        for i,(ego_x,other_x,speed) in enumerate(((0,0,4),(0,0,2),(12,12,1))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"ego_road_id":7,
                         "yield_sign_id":25,"ego_speed_mps":speed,
                         "ego_body_before_yield_reference":i<2,
                         "ego_body_vertices_xy_m":body(ego_x),
                         "other_body_vertices_xy_m":body(other_x)})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"],
                 "camera_frame_ids":{name:r["frame"] for name in cameras}} for i,r in enumerate(rows)]
        (root/"entry_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_yield_response_and_other_entrance_obligation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["observed_slowed_or_stopped_before_reference"])
            self.assertTrue(result["other_not_obligated_by_stop_or_yield"])
            self.assertTrue(result["other_inside_at_ego_entry"])
            self.assertEqual(result["subsection_one_reference"]["reference_kind"],"marked_stop_line")
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,"stop")
            self.assertFalse(measure.analyze(root)["other_not_obligated_by_stop_or_yield"])

    def test_subsection_one_ordered_reference_and_source_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            review=json.loads((root/"site_review.json").read_text())
            review["marked_stop_line_observed"]=False
            (root/"site_review.json").write_text(json.dumps(review))
            self.assertEqual(measure.analyze(root)["subsection_one_reference"]["reference_kind"],"near_crosswalk")
            review["near_crosswalk_observed"]=False
            (root/"site_review.json").write_text(json.dumps(review))
            self.assertEqual(measure.analyze(root)["subsection_one_reference"]["reference_kind"],"nearest_view_point")
            review["nearest_view_point_xy_m"]=None
            (root/"site_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"Nearest-view"):
                measure.analyze(root)
            self.fixture(root)
            (root/"approach.mkv").write_text("changed camera")
            with self.assertRaisesRegex(ValueError,"camera source changed"):
                measure.analyze(root)
            self.fixture(root)
            context=json.loads((root/"intersection_context.json").read_text())
            context["native_yield_sign_id"]=26
            (root/"intersection_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,"context changed after review"):
                measure.analyze(root)

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
            with self.assertRaisesRegex(ValueError,"frame"):measure.analyze(root)

    def test_all_native_entrances_must_have_reviewed_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/"intersection_context.json").read_text())
            ctx["entrances"].pop()
            (root/"intersection_context.json").write_text(json.dumps(ctx))
            review=json.loads((root/"site_review.json").read_text())
            review["intersection_context_sha256"]=hashlib.sha256((root/"intersection_context.json").read_bytes()).hexdigest()
            (root/"site_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"Incomplete entrance device inventory"):
                measure.analyze(root)

    def test_officer_exception_requires_original_control_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/"intersection_context.json").read_text())
            ctx["case_id"]="testing__C158208__NRS-484B-257-2__motor_vehicle_driver__officer_control_exception"
            ctx["police_control"]=True
            (root/"intersection_context.json").write_text(json.dumps(ctx))
            review=json.loads((root/"site_review.json").read_text())
            review["intersection_context_sha256"]=hashlib.sha256((root/"intersection_context.json").read_bytes()).hexdigest()
            (root/"site_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"Missing original officer-control review"):
                measure.analyze(root)
            officer={"intersection_context_sha256":review["intersection_context_sha256"],
                     "camera_sha256":review["camera_sha256"],
                     "reviewed_carla_frames":[100,101,102],"officer_actor_id":99,
                     "control_observed_at_entry":True,"authority_judgment":"unresolved"}
            (root/"officer_review.json").write_text(json.dumps(officer))
            self.assertTrue(measure.analyze(root)["officer_control_observed"])
            officer["control_observed_at_entry"]=False
            (root/"officer_review.json").write_text(json.dumps(officer))
            with self.assertRaisesRegex(ValueError,"complete original-source control review"):
                measure.analyze(root)

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
