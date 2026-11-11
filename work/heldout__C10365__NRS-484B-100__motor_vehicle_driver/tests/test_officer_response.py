from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("officer_response", HERE/"officer_response.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
spec2=importlib.util.spec_from_file_location("officer_comparison_audit", HERE/"officer_comparison_audit.py")
audit_module=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(audit_module)
ACTOR="motor_vehicle_driver"

class OfficerResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.context={"actor_role":ACTOR,"officer_role":"police_officer","officer_id":"officer-1","subject_id":"subject-1",
                      "duty_source":"authored-duty-context.json","lawfulness_source":"pending-original-review.json"}
        self.direction={"officer_id":"officer-1","subject_id":"subject-1","frame":1,"indication_source":"officer-indication.json","command":"stop"}
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

if __name__=="__main__":unittest.main()
