from __future__ import annotations
import importlib.util
import json
import hashlib
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]

def load(name):
    s = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

measure = load("overtaken_response").measure
verify_saved_sources = load("overtaken_response").verify_saved_sources
measure_observed_saved = load("overtaken_response").measure_observed_saved
measure_audible_saved = load("overtaken_response").measure_audible_saved
audit = load("overtaken_comparison_audit").audit
saved_behavior = load("overtaken_saved_behavior_audit")
pass_gap = load("pass_gap_audit")
controller = load("overtaken_controller")
sys.path.insert(0, str(HERE))
native = load("overtaken_native")
finalizer = load("overtaken_finalizer")

class OvertakenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = {"subject_id":"ego","overtaker_id":"passing-car","road_source":"original-lane-readback",
                        "actor_source":"original-participant-readback","right_pass_permitted":False,
                        "right_pass_permission_source":"source-context-pending-legal-review","legal_conclusion":None}
        self.events = {"subject_id":"ego","overtaker_id":"passing-car","notice_frame":1,
                       "pass_complete_frame":4,"notice_kind":"audible_signal","notice_source":"original-signal-stream"}
        self.motion = {"frames":[{"frame":i,"subject_id":"ego","overtaker_id":"passing-car",
                                  "speed_mps":speed,"right_offset_m":offset}
                                 for i,(speed,offset) in enumerate(((5,0),(5,0),(5,.5),(5,1),(5,1)))]}
    def write(self, name, obj):
        p = self.root / name; p.write_text(json.dumps(obj)); return p
    def measure(self):
        return measure(self.write("context.json",self.context),self.write("events.json",self.events),self.write("motion.json",self.motion))
    def measure_variant(self, name):
        return measure(self.write(name+"-context.json",self.context),
                       self.write(name+"-events.json",self.events),
                       self.write(name+"-motion.json",self.motion))
    def test_measures_both_clauses_without_legal_label(self):
        r=self.measure();self.assertEqual(r["max_right_shift_m"],1)
        self.assertEqual(r["max_precompletion_speed_delta_mps"],0)
        self.assertIsNone(r["legal_conclusion"])
    def test_source_and_notice_rejections(self):
        self.context["right_pass_permission_source"]=""
        with self.assertRaisesRegex(ValueError,"sourced premise"):self.measure()
        self.context["right_pass_permission_source"]="context"
        self.events["notice_kind"]="assumed"
        with self.assertRaisesRegex(ValueError,"notice source"):self.measure()
    def test_missing_precompletion_and_wrong_actor(self):
        self.motion["frames"]=self.motion["frames"][:2]+self.motion["frames"][4:]
        with self.assertRaisesRegex(ValueError,"no motion samples"):self.measure()
        self.motion["frames"][1]["overtaker_id"]="other"
        with self.assertRaisesRegex(ValueError,"identities differ"):self.measure()
    def test_comparisons_check_held_conditions(self):
        first=self.measure_variant("first")
        self.motion["frames"][3]["right_offset_m"]=2
        second=self.measure_variant("second")
        p=self.write("first-result.json",first);q=self.write("second-result.json",second)
        self.assertTrue(audit([p,q],"right_shift")["comparison_complete"])
        self.motion["frames"][2]["speed_mps"]=6
        second=self.measure_variant("changed-speed");self.write("second-result.json",second)
        with self.assertRaisesRegex(ValueError,"held motion"):audit([p,q],"right_shift")
        self.motion["frames"][2]["speed_mps"]=5
        self.motion["frames"][3]["right_offset_m"]=1
        self.context["right_pass_permitted"]=True
        second=self.measure_variant("exception");self.write("second-result.json",second)
        self.assertTrue(audit([p,q],"right_pass_exception")["comparison_complete"])
    def test_comparison_rejects_changed_original_source(self):
        first=self.measure_variant("first")
        self.motion["frames"][3]["right_offset_m"]=2
        second=self.measure_variant("second")
        p=self.write("first-result.json",first);q=self.write("second-result.json",second)
        self.write("motion.json",{"frames":[]})
        self.write("first-motion.json",{"frames":[]})
        with self.assertRaisesRegex(ValueError,"original source changed"):
            audit([p,q],"right_shift")
    def test_speed_and_notice_comparisons(self):
        first=self.measure_variant("first");p=self.write("first-result.json",first)
        self.motion["frames"][2]["speed_mps"]=6
        second=self.measure_variant("speed");q=self.write("second-result.json",second)
        self.assertTrue(audit([p,q],"speed_hold_until_complete")["comparison_complete"])
        self.motion["frames"][2]["speed_mps"]=5
        self.events["notice_kind"]="observed_vehicle"
        self.events["notice_source"]="original-visibility-stream"
        second=self.measure_variant("observed");self.write("second-result.json",second)
        self.assertTrue(audit([p,q],"notice_modality")["comparison_complete"])
        self.motion["frames"][3]["right_offset_m"]=2
        second=self.measure_variant("observed-changed-motion");self.write("second-result.json",second)
        with self.assertRaisesRegex(ValueError,"held motion"):
            audit([p,q],"notice_modality")
    def test_comparison_rejects_fabricated_measurement(self):
        first=self.measure_variant("first")
        self.motion["frames"][3]["right_offset_m"]=2
        second=self.measure_variant("second")
        second["max_right_shift_m"]=4
        p=self.write("first-result.json",first);q=self.write("second-result.json",second)
        with self.assertRaisesRegex(ValueError,"measurement differs"):
            audit([p,q],"right_shift")
    def test_saved_right_pass_requires_distinct_sourced_premise(self):
        receipts = [HERE/"no-right-primary-saved-processing.json",
                    HERE/"right-pass-primary-saved-processing.json"]
        with self.assertRaisesRegex(ValueError,"lacks original permission premise"):
            saved_behavior.audit_right_pass_exception(*receipts)
        staged = []
        roots = []
        for index, receipt_path in enumerate(receipts):
            receipt = json.loads(receipt_path.read_text())
            source = Path(receipt["analysis_directory"])
            root = self.root/("permission-base" if index == 0 else "permission-variant")
            root.mkdir()
            for name in saved_behavior.SOURCE_NAMES+("analysis-report.json","result.json"):
                shutil.copy2(source/name,root/name)
            rule=root/"right_pass_governing_rule.txt"
            rule.write_text("Synthetic governing-rule fixture; no legal finding.\n")
            survey=root/"right_pass_road_survey.json"
            survey.write_text(json.dumps({"source_kind":"original_road_survey",
                "road_id":"synthetic-road","lane_ids":[1] if index == 0 else [1,2],
                "passing_side":"right","source_provenance":"synthetic diagnostic"})+"\n")
            premise=root/"right_pass_premise.json"
            premise.write_text(json.dumps({"source_kind":"reviewed_right_pass_premise",
                "permission_state":bool(index),"review_scope":"comparison premise only",
                "legal_conclusion":None,"governing_rule_citation":"synthetic fixture",
                "governing_rule_sha256":hashlib.sha256(rule.read_bytes()).hexdigest(),
                "road_survey_sha256":hashlib.sha256(survey.read_bytes()).hexdigest()})+"\n")
            for path in (rule,survey,premise):
                receipt["original_source_hashes"][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            receipt["analysis_directory"]=str(root)
            staged_path=root/"receipt.json";staged_path.write_text(json.dumps(receipt))
            staged.append(staged_path);roots.append(root)
        checked=saved_behavior.audit_right_pass_exception(*staged)
        self.assertTrue(checked["comparison_complete"])
        self.assertTrue(checked["diagnostic_fixture_only"])
        survey=roots[1]/"right_pass_road_survey.json"
        survey.write_text(survey.read_text()+"tamper")
        with self.assertRaisesRegex(ValueError,"source missing or changed"):
            saved_behavior.audit_right_pass_exception(*staged)
    def test_exact_controller_targets_and_native_call(self):
        for suffix in controller.CASES:
            expected_notice,right_pass,right_shift,early = controller.CASES[suffix]
            before=controller.target(suffix,notice_kind=None,notice_source=None,pass_complete=False)
            self.assertEqual(before["target_right_offset_m"],0)
            self.assertEqual(before["target_speed_mps"],5)
            active=controller.target(suffix,notice_kind=expected_notice,notice_source="original-event",pass_complete=False)
            self.assertEqual(active["target_right_offset_m"],right_shift if not right_pass else 0)
            self.assertEqual(active["target_speed_mps"],6 if early else 5)
            self.assertEqual(controller.target(suffix,notice_kind=expected_notice,notice_source="original-event",pass_complete=True)["target_speed_mps"],6)
            class FakeVehicle:
                control=None
                def apply_control(self,control): self.control=control
            car=FakeVehicle()
            command=controller.apply(car,dict,active,right_offset_m=0,speed_mps=4)
            self.assertEqual(car.control,command)
            self.assertGreater(command["throttle"],0)
            self.assertLess(command["steer"],0) if active["target_right_offset_m"] else self.assertEqual(command["steer"],0)
        with self.assertRaisesRegex(ValueError,"Notice mode"):
            controller.target("observed_gives_way_holds_speed",notice_kind="audible_signal",notice_source="original-event",pass_complete=False)

    def test_native_plan_all_cases_and_source_readback(self):
        plan=json.loads((HERE/"case-plan.json").read_text())
        for suffix in controller.CASES:
            case_id=native.PREFIX+suffix
            self.assertEqual(native.check_plan(plan,case_id),suffix)
        with self.assertRaisesRegex(ValueError,"Unselected"):
            native.check_plan(plan,native.PREFIX+"invented")
        class V:
            def __init__(self,x,y=0,z=0):self.x,self.y,self.z=x,y,z
        class Transform:
            def __init__(self,x):self.location=V(x)
            def get_forward_vector(self):return V(1)
        class Box:
            def __init__(self,x):self.x=x
            def get_world_vertices(self,transform):
                return [V(self.x+dx,dy,z) for dx in (-1,1) for dy in (-.5,.5) for z in (0,1)]
        class Actor:
            def __init__(self,x,name):self.x,self.id=x,name;self.bounding_box=Box(x)
            def get_transform(self):return Transform(self.x)
            def get_velocity(self):return V(5)
        class Waypoint:
            transform=Transform(0)
        subject,passing=Actor(0,"subject"),Actor(-3,"passing")
        row=native.readback(subject,passing,Waypoint(),101,0.05,notice_stimulus=True)
        self.assertFalse(row["body_pass_complete"])
        self.assertIsNone(row["notice_observed"])
        self.assertIsNone(row["right_pass_permission_verified"])
        passing.x=3;passing.bounding_box=Box(3)
        self.assertTrue(native.readback(subject,passing,Waypoint(),102,0.1,notice_stimulus=True)["body_pass_complete"])
        passing.bounding_box=Box(float("nan"))
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            native.readback(subject,passing,Waypoint(),103,0.15,notice_stimulus=True)

    def test_generated_signal_source_keeps_hearing_unverified(self):
        off, silent=native.generated_signal_rows(2,100,.05,False)
        on, sounding=native.generated_signal_rows(2,101,.10,True)
        self.assertEqual((off["horn_command_requested"],on["horn_command_requested"]),(False,True))
        self.assertEqual((silent["generated_rms"],sounding["generated_rms"]),(0.0,.6))
        self.assertEqual((on["frame"],sounding["frame"]),(101,101))
        self.assertIsNone(sounding["subjective_hearing_confirmed"])
        with self.assertRaisesRegex(ValueError,"signal frame"):
            native.generated_signal_rows(2,101,float("nan"),True)

    def test_saved_source_join_recomputes_motion_and_pass_completion(self):
        def corners(x):return [[x-1,-.5],[x+1,-.5],[x+1,.5],[x-1,.5]]
        bodies=[];mapping=[];trace=[]
        for index,other_x in enumerate((-4,0,2,4)):
            frame=100+index;time_s=index*.05
            bodies.append({"frame":frame,"time_s":time_s,"subject_id":"subject",
                "overtaker_id":"overtaker","subject_corners":corners(0),
                "overtaker_corners":corners(other_x),"road_tangent_xy":[1,0],
                "road_waypoint_xy":[0,0],"subject_pose_xy":[0,0],
                "subject_speed_mps":5,"subject_right_offset_m":0,
                "body_pass_complete":index==3,"notice_stimulus":index>0,
                "notice_observed":None,"right_pass_permission_verified":None})
            mapping.append({"video_frame":index,"carla_frame":frame,"time_s":time_s})
            trace.append({"frame":frame,"time_s":time_s,"speed_mps":5})
        def sources():
            paths=[]
            for name,rows in (("overtaken_source.jsonl",bodies),
                              ("video_frames.jsonl",mapping),("trace.jsonl",trace)):
                path=self.root/name;path.write_text("".join(json.dumps(row)+"\n" for row in rows));paths.append(path)
            return paths
        paths=sources()
        report=verify_saved_sources(*paths)
        self.assertEqual([row["body_pass_complete"] for row in report["frames"]],[False,False,False,True])
        gap_report=pass_gap.audit(*paths)
        self.assertEqual([row["signed_gap_m"] for row in gap_report["frames"]],[-6,-2,0,2])
        self.assertEqual(gap_report["first_positive_gap_frame"],103)
        self.assertFalse(gap_report["physical_acceptance_claimed"])
        self.assertIsNone(report["frames"][1]["notice_observed"])
        with self.assertRaisesRegex(ValueError,"visibility notice"):
            measure_observed_saved(*paths)
        bodies[1]["visibility_relation"]={"a":"subject","b":"overtaker",
            "visible":True,"rays":[{"clear":True,"blockers":[]}]}
        bodies[1]["notice_observed"]=True;sources()
        self.assertTrue(verify_saved_sources(*paths)["frames"][1]["notice_observed"])
        observed=measure_observed_saved(*paths)
        self.assertEqual((observed["notice_frame"],observed["pass_complete_frame"]),(101,103))
        self.assertEqual(observed["max_precompletion_speed_delta_mps"],0)
        self.assertIsNone(observed["legal_conclusion"])
        self.write("config.json",{"selected_case_id":finalizer.CASE_ID,
            "law_id":"NRS-484B-207-2","cell_id":"C179789","actor":"motor_vehicle_driver",
            "case":{"recording_description":{"channels":[],"context_inputs":[],"limitations":[]}}})
        report=finalizer.analyze(self.root)
        self.assertEqual(report["measurements"]["right_shift_m"]["value"],observed["max_right_shift_m"])
        self.assertEqual(report["measurements"]["speed_delta_mps"]["value"],0)
        self.assertEqual(report["measurements"]["pass_complete_frame"]["value"],103)
        result=finalizer.build_result(self.root,report)
        self.assertEqual(result["case_id"],finalizer.CASE_ID)
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertEqual(len(result["recording_evidence"]),2)
        observed_visibility=bodies[1]["visibility_relation"]
        bodies[1]["visibility_relation"]=None
        bodies[1]["notice_observed"]=None
        sources()
        command=[];envelope=[]
        for index,row in enumerate(bodies):
            c,e=native.generated_signal_rows("overtaker",row["frame"],row["time_s"],index>0)
            command.append(c);envelope.append(e)
        cp=self.root/"signal_command_original.jsonl"
        ep=self.root/"signal_audio_envelope_original.jsonl"
        cp.write_text("".join(json.dumps(row)+"\n" for row in command))
        ep.write_text("".join(json.dumps(row)+"\n" for row in envelope))
        audible=measure_audible_saved(*paths,cp,ep)
        self.assertEqual((audible["notice_frame"],audible["pass_complete_frame"]),(101,103))
        self.assertIsNone(audible["hearing_confirmed"])
        envelope[1]["subjective_hearing_confirmed"]=True
        ep.write_text("".join(json.dumps(row)+"\n" for row in envelope))
        with self.assertRaisesRegex(ValueError,"signal/frame join"):
            measure_audible_saved(*paths,cp,ep)
        envelope[1]["subjective_hearing_confirmed"]=None
        ep.write_text("".join(json.dumps(row)+"\n" for row in envelope))
        self.write("config.json",{"selected_case_id":finalizer.AUDIBLE_CASE_ID,
            "law_id":"NRS-484B-207-2","cell_id":"C179789","actor":"motor_vehicle_driver",
            "case":{"recording_description":{"channels":[],"context_inputs":[],"limitations":[]}}})
        audible_report=finalizer.analyze(self.root)
        self.assertEqual(audible_report["measurements"]["pass_complete_frame"]["value"],103)
        self.assertIsNone(audible_report["measurements"]["overtaken_response"]["value"]["hearing_confirmed"])
        bodies[1]["visibility_relation"]=observed_visibility
        bodies[1]["notice_observed"]=True
        sources()
        sys.path.insert(0,str(HERE.parents[1]/"runtime/scenario_pipeline"))
        from worker_exchange.native_output import validate_result
        validate_result(result)
        bodies[1]["visibility_relation"]["visible"]=False;sources()
        with self.assertRaisesRegex(ValueError,"visibility rays"):
            verify_saved_sources(*paths)
        bodies[1]["visibility_relation"]=None;bodies[1]["notice_observed"]=None
        bodies[1]["body_pass_complete"]=True;sources()
        with self.assertRaisesRegex(ValueError,"pass-completion"):
            verify_saved_sources(*paths)
        bodies[1]["body_pass_complete"]=False
        bodies[1]["subject_right_offset_m"]=1;sources()
        with self.assertRaisesRegex(ValueError,"right-offset"):
            verify_saved_sources(*paths)
        bodies[1]["subject_right_offset_m"]=0
        trace[1]["speed_mps"]=6;sources()
        with self.assertRaisesRegex(ValueError,"speed/trace"):
            verify_saved_sources(*paths)
        trace[1]["speed_mps"]=5
        mapping[1]["carla_frame"]=999;sources()
        with self.assertRaisesRegex(ValueError,"frame-map join"):
            verify_saved_sources(*paths)

if __name__ == "__main__": unittest.main()
