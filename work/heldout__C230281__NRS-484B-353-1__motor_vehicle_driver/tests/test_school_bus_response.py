from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,H/(n+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load("school_bus_response").measure
audit=load("school_bus_comparison_audit").audit
class SchoolBusTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.p=Path(t.name)
  self.c={"subject_id":"ego","bus_id":"bus","approach_direction":"meeting","road_source":"original-road-readback","bus_equipment_source":"original-bus-readback","pupil_stop_source":"original-stop-context","bus_stopped_for_pupils":True,"bus_required_equipment":True,"divided_highway":False,"other_roadway":False,"traffic_officer_controlled":False,"officer_control_source":"original-officer-context","legal_conclusion":None}
  self.s={"bus_id":"bus","source":"original-signal-readback","red_on_frame":1,"red_off_frame":4,"front_visible":True,"rear_visible":True}
  self.m={"rate_hz":20,"frames":[{"frame":i,"subject_id":"ego","speed_mps":v,"passed_bus":False} for i,v in enumerate((3,2,0,0,2))]}
 def write(self,n,o):
  p=self.p/n;p.write_text(json.dumps(o));return p
 def measure(self):return measure(self.write("context.json",self.c),self.write("signal.json",self.s),self.write("motion.json",self.m))
 def test_meeting_and_overtaking_motion(self):
  a=self.measure();self.assertTrue(a["observed_stop_during_red"]);self.assertFalse(a["observed_pass_before_red_ceased"])
  self.assertEqual(a["first_stop_frame"],2);self.assertEqual(a["stop_latency_s"],.05)
  self.assertTrue(a["observed_held_until_red_ceased"]);self.assertFalse(a["observed_early_restart_during_red"])
  self.c["approach_direction"]="overtaking";b=self.measure();self.assertEqual(b["approach_direction"],"overtaking")
  self.assertIsNone(b["legal_conclusion"])
 def test_missing_signal_and_exception_sources_rejected(self):
  self.s["rear_visible"]=False
  with self.assertRaisesRegex(ValueError,"front and rear"):self.measure()
  self.s["rear_visible"]=True;self.c["other_roadway"]=True
  with self.assertRaisesRegex(ValueError,"divided highway"):self.measure()
  self.c["other_roadway"]=False;self.c["officer_control_source"]=""
  with self.assertRaisesRegex(ValueError,"officer-control"):self.measure()
 def test_comparison_rejects_changed_held_condition(self):
  a=self.measure();self.m["frames"][2]["speed_mps"]=1;self.m["frames"][3]["speed_mps"]=1;self.m["frames"][3]["passed_bus"]=True;self.m["frames"][4]["passed_bus"]=True;b=self.measure()
  p=self.write("first.json",a);q=self.write("second.json",b)
  self.assertTrue(audit([p,q],"response")["comparison_complete"])
  b["other_roadway"]=True;self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"held condition"):audit([p,q],"response")
 def test_red_cessation_restart_compared_separately(self):
  a=self.measure();self.m["frames"][4]["speed_mps"]=0;b=self.measure()
  p=self.write("first.json",a);q=self.write("second.json",b)
  self.assertTrue(audit([p,q],"red_cessation_restart")["comparison_complete"])
  b["first_stop_frame"]=3;b["stop_latency_s"]=.1;self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"held condition"):audit([p,q],"red_cessation_restart")
 def test_early_restart_and_pass_transition(self):
  self.m["frames"][3]["speed_mps"]=1
  self.m["frames"][3]["passed_bus"]=True
  self.m["frames"][4]["passed_bus"]=True
  o=self.measure();self.assertTrue(o["observed_early_restart_during_red"])
  self.assertTrue(o["observed_pass_before_red_ceased"]);self.assertFalse(o["observed_held_until_red_ceased"])
  self.assertEqual(o["first_pass_frame"],3)
 def test_premature_restart_isolated_from_pass_and_cessation(self):
  a=self.measure();self.m["frames"][3]["speed_mps"]=1;b=self.measure()
  self.assertFalse(b["observed_pass_before_red_ceased"])
  p=self.write("first.json",a);q=self.write("second.json",b)
  self.assertTrue(audit([p,q],"premature_restart")["comparison_complete"])
  b["observed_motion_after_red_ceased"]=False;self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"held condition"):audit([p,q],"premature_restart")
 def test_temporal_source_rejections(self):
  self.m.pop("rate_hz")
  with self.assertRaisesRegex(ValueError,"frame rate"):self.measure()
  self.m["rate_hz"]=20
  self.m["frames"][1]["passed_bus"]=True
  with self.assertRaisesRegex(ValueError,"already passed"):self.measure()
  self.m["frames"][1]["passed_bus"]=False
  self.m["frames"][2]["passed_bus"]=True
  with self.assertRaisesRegex(ValueError,"reverses"):self.measure()
  self.m["frames"][2]["passed_bus"]=False
  self.m["frames"][3]["speed_mps"]=float("nan")
  with self.assertRaisesRegex(ValueError,"original subject motion"):self.measure()
 def test_comparison_rejects_fabricated_timing(self):
  a=self.measure();b=dict(a);b["stop_latency_s"]=10
  p=self.write("first.json",a);q=self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"stop latency"):audit([p,q],"response")
 def test_comparison_rejects_changed_original_signal_hash(self):
  a=self.measure();self.m["frames"][3]["speed_mps"]=1;b=self.measure()
  b["source_sha256"]=dict(b["source_sha256"],signal="0"*64)
  p=self.write("first.json",a);q=self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"signal source changed"):audit([p,q],"premature_restart")
if __name__=="__main__":unittest.main()
