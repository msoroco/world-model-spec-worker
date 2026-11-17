from __future__ import annotations
import importlib.util
import json
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
audit = load("overtaken_comparison_audit").audit
controller = load("overtaken_controller")
sys.path.insert(0, str(HERE))
native = load("overtaken_native")

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

if __name__ == "__main__": unittest.main()
