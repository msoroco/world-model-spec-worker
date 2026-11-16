from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
import types
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("officer_response", HERE/"officer_response.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
spec2=importlib.util.spec_from_file_location("officer_comparison_audit", HERE/"officer_comparison_audit.py")
audit_module=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(audit_module)
spec3=importlib.util.spec_from_file_location("pedestrian_runner", HERE/"runner.py")
runner=importlib.util.module_from_spec(spec3);spec3.loader.exec_module(runner)
sys.modules["runner"] = runner
ACTOR="pedestrian"

class OfficerResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.context={"actor_role":ACTOR,"officer_role":"police_officer","officer_id":"officer-1","subject_id":"subject-1",
                      "duty_source":"authored-duty-context.json","lawfulness_source":"pending-original-review.json"}
        self.direction={"officer_id":"officer-1","subject_id":"subject-1","recipient_id":"subject-1",
                        "frame":1,"indication_source":"officer-indication.json","command":"stop",
                        "exact_direction_text":"Wait at the marked sidewalk location until released",
                        "wait_location_source":"sidewalk-location.json","communication_modality":"visual",
                        "communication_source":"original-camera-source.mkv",
                        "opportunity_source":"officer-subject-sightline.json","actual_perception":None}
        self.motion={"frames":[{"frame":i,"subject_id":"subject-1","speed_mps":s} for i,s in enumerate((2,2,1,0))]}
    def write(self,name,obj):
        p=self.root/name;p.write_text(json.dumps(obj));return p
    def measure(self,command="stop"):
        return module.measure(self.write("context.json",self.context),self.write("direction.json",self.direction),self.write("motion.json",self.motion),expected_actor=ACTOR,expected_command=command)
    def test_stop_observation_keeps_legal_question_open(self):
        r=self.measure();self.assertEqual(r["observed_response"],"stopped_after_indication")
        self.assertIsNone(r["willfulness_conclusion"])
    def test_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError,"missing required source"):
            module.measure(self.root/"absent.json",self.root/"absent2.json",self.root/"absent3.json",expected_actor=ACTOR,expected_command="stop")
    def test_unaddressed_and_unsourced_rejected(self):
        self.direction["subject_id"]="other"
        with self.assertRaisesRegex(ValueError,"source-bound"):self.measure()
        self.direction["subject_id"]="subject-1";self.context["lawfulness_source"]=""
        with self.assertRaisesRegex(ValueError,"source references"):self.measure()
    def test_exact_direction_and_perception_sources_required(self):
        self.direction["wait_location_source"]=""
        with self.assertRaisesRegex(ValueError,"wait location"):self.measure()
        self.direction["wait_location_source"]="sidewalk-location.json"
        self.direction["communication_modality"]="unspecified"
        with self.assertRaisesRegex(ValueError,"modality"):self.measure()
        self.direction["communication_modality"]="visual"
        self.direction["actual_perception"]=True
        with self.assertRaisesRegex(ValueError,"perception"):self.measure()
    def test_response_span_and_legal_assertion_rejected(self):
        self.motion["frames"]=self.motion["frames"][:2]
        with self.assertRaisesRegex(ValueError,"span|post-indication"):self.measure()
        self.motion["frames"].extend([{"frame":2,"subject_id":"subject-1","speed_mps":1},{"frame":3,"subject_id":"subject-1","speed_mps":0}])
        self.context["willfulness_conclusion"]=True
        with self.assertRaisesRegex(ValueError,"willfulness"):self.measure()
    def test_controlled_comparison_rejects_changed_fixed_condition(self):
        first=self.measure();first["observed_response"]="no_observed_stop"
        second=self.measure()
        p1=self.write("first-result.json",first);p2=self.write("second-result.json",second)
        ok=audit_module.audit([p1,p2],expected_actor=ACTOR,expected_command="stop",fixed_subject_id="subject-1",fixed_officer_id="officer-1")
        self.assertTrue(ok["comparison_complete"])
        second["officer_id"]="other";self.write("second-result.json",second)
        with self.assertRaisesRegex(ValueError,"fixed subject or officer"):
            audit_module.audit([p1,p2],expected_actor=ACTOR,expected_command="stop",fixed_subject_id="subject-1",fixed_officer_id="officer-1")
        second["officer_id"]="officer-1";second["wait_location_source"]="other-sidewalk.json";self.write("second-result.json",second)
        with self.assertRaisesRegex(ValueError,"condition changed"):
            audit_module.audit([p1,p2],expected_actor=ACTOR,expected_command="stop",fixed_subject_id="subject-1",fixed_officer_id="officer-1")

class PedestrianNativeConstructionTests(unittest.TestCase):
    def test_all_four_exact_cases_have_distinct_post_direction_controls(self):
        for suffix,(command,responds) in runner.CASES.items():
            case=runner.PREFIX+suffix
            cfg={"law_id":"NRS-484B-100","cell_id":"C111305","actor":"pedestrian",
                 "selected_case_id":case,"case":{"case_id":case},"rate_hz":20,"frames":160,
                 "direction_frame":40,"cameras":[{"name":name,"width":spec[2][0],"height":spec[2][1]}
                                                   for name,spec in runner.CAMERAS.items()]}
            self.assertEqual(runner.check_config(cfg),(command,responds))
            self.assertNotEqual(runner.walker_speed(command,True,40,40,1.2),
                                runner.walker_speed(command,False,40,40,1.2))
            cfg["selected_case_id"]="wrong"
            with self.assertRaisesRegex(ValueError,"Unknown exact"):runner.check_config(cfg)
    def test_crosswalk_requires_connected_sidewalk_and_junction(self):
        Point=lambda x,y:types.SimpleNamespace(x=x,y=y,z=0)
        p=[Point(0,0),Point(0,2),Point(8,2),Point(8,0),Point(0,0)]
        class Map:
            def __init__(self):self.junction=True;self.sidewalk=True
            def get_crosswalks(self):return p
            def get_waypoint(self,point,**kwargs):
                if kwargs["lane_type"]=="sidewalk":
                    return types.SimpleNamespace(transform=types.SimpleNamespace(location=point)) if self.sidewalk else None
                return types.SimpleNamespace(is_junction=self.junction)
        carla=types.SimpleNamespace(LaneType=types.SimpleNamespace(Sidewalk="sidewalk",Driving="driving"),
                                    Location=lambda x,y,z:Point(x,y))
        world=Map()
        first,last,start,end,direction=runner.choose_crosswalk(world,carla)
        self.assertGreaterEqual((last.x-first.x)**2+(last.y-first.y)**2,16)
        self.assertAlmostEqual(sum(value*value for value in direction),1)
        world.junction=False
        with self.assertRaisesRegex(ValueError,"crosswalk"):runner.choose_crosswalk(world,carla)
        world.junction=True;world.sidewalk=False
        with self.assertRaisesRegex(ValueError,"sidewalk"):runner.choose_crosswalk(world,carla)
    def test_officer_gesture_uses_actual_walker_bone_api(self):
        class Walker:
            def get_bones(self):return types.SimpleNamespace(bone_transforms=[("upperarm_r",None,None,None)])
            def set_bones(self,value):self.bones=value
            def blend_pose(self,value):self.blend=value
        carla=types.SimpleNamespace(Location=lambda *args:None,Rotation=lambda **kw:kw,
                                    Transform=lambda loc,rot:(loc,rot),WalkerBoneControlIn=lambda rows:rows)
        officer=Walker();stop=runner.pose_direction(carla,officer,"stop")
        proceed=runner.pose_direction(carla,officer,"proceed")
        self.assertNotEqual(stop["relative_pitch_deg"],proceed["relative_pitch_deg"])
        self.assertEqual(officer.blend,1.0)

class SavedSourceTests(unittest.TestCase):
    def test_original_join_and_missing_camera_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            case=runner.PREFIX+"stop_responds"
            cfg={"law_id":"NRS-484B-100","cell_id":"C111305","actor":"pedestrian",
                 "selected_case_id":case,"case":{"case_id":case},"rate_hz":20,"frames":160,
                 "direction_frame":40,"cameras":[{"name":name,"width":spec[2][0],"height":spec[2][1]}
                                                   for name,spec in runner.CAMERAS.items()]}
            (root/"config.json").write_text(json.dumps(cfg))
            context={"actor_role":"pedestrian","officer_role":"police_officer","officer_id":"officer-1",
                     "subject_id":"subject-1","duty_source":"source pending review","lawfulness_source":"source pending review"}
            direction={"officer_id":"officer-1","subject_id":"subject-1","recipient_id":"subject-1",
                       "frame":2,"indication_source":"original arm cue","command":"stop",
                       "exact_direction_text":"Wait at marked sidewalk until released",
                       "wait_location_source":"sidewalk waypoint","communication_modality":"visual",
                       "communication_source":"overview.mkv","opportunity_source":"four cameras",
                       "actual_perception":None}
            motion=[{"frame":i,"time_s":i/20,"subject_id":"subject-1","speed_mps":speed,
                     "position_m":[i/10,0,0]} for i,speed in enumerate((1.2,1.2,1.2,.5,0))]
            (root/"officer_context.json").write_text(json.dumps(context))
            (root/"officer_direction.json").write_text(json.dumps(direction))
            (root/"subject_motion.json").write_text(json.dumps({"frames":motion}))
            (root/"subject_motion_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in motion))
            (root/"video_frames.jsonl").write_text("".join(json.dumps({"video_frame":i,"carla_frame":i,"time_s":i/20})+"\n" for i in range(5)))
            (root/"trace.jsonl").write_text("".join(json.dumps({"frame":i,"time_s":i/20})+"\n" for i in range(5)))
            for name in runner.CAMERAS:(root/(name+".mkv")).write_bytes(b"text-only test marker")
            report=module.analyze_saved(root)
            self.assertEqual(report["measurements"]["officer_response"]["value"]["observed_response"],"stopped_after_indication")
            self.assertEqual(len((root/"subject_speed_mps.jsonl").read_text().splitlines()),5)
            (root/"overview.mkv").unlink()
            with self.assertRaisesRegex(ValueError,"Missing required source: overview.mkv"):
                module.analyze_saved(root)
            (root/"overview.mkv").write_bytes(b"text-only test marker")
            motion[1]["frame"]=99
            (root/"subject_motion_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in motion))
            with self.assertRaisesRegex(ValueError,"frame join differs"):
                module.analyze_saved(root)

if __name__=="__main__":unittest.main()
