from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]

def load(name):
    s = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

measure = load("overtaken_response").measure
audit = load("overtaken_comparison_audit").audit

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
        first=self.measure();second=dict(first);second["max_right_shift_m"]=2
        p=self.write("first-result.json",first);q=self.write("second-result.json",second)
        self.assertTrue(audit([p,q],"right_shift")["comparison_complete"])
        second["max_precompletion_speed_delta_mps"]=1;self.write("second-result.json",second)
        with self.assertRaisesRegex(ValueError,"held motion"):audit([p,q],"right_shift")
        second=dict(first);second["right_pass_permitted_premise"]=True;self.write("second-result.json",second)
        self.assertTrue(audit([p,q],"right_pass_exception")["comparison_complete"])

if __name__ == "__main__": unittest.main()
