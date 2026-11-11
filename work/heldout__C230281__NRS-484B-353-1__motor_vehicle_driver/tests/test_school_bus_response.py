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
  self.m={"frames":[{"frame":i,"subject_id":"ego","speed_mps":v,"passed_bus":False} for i,v in enumerate((3,2,0,0,2))]}
 def write(self,n,o):
  p=self.p/n;p.write_text(json.dumps(o));return p
 def measure(self):return measure(self.write("context.json",self.c),self.write("signal.json",self.s),self.write("motion.json",self.m))
 def test_meeting_and_overtaking_motion(self):
  a=self.measure();self.assertTrue(a["observed_stop_during_red"]);self.assertFalse(a["observed_pass_before_red_ceased"])
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
  a=self.measure();b=dict(a);b["observed_stop_during_red"]=False;b["observed_pass_before_red_ceased"]=True
  p=self.write("first.json",a);q=self.write("second.json",b)
  self.assertTrue(audit([p,q],"response")["comparison_complete"])
  b["other_roadway"]=True;self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"held condition"):audit([p,q],"response")
 def test_red_cessation_restart_compared_separately(self):
  a=self.measure();b=dict(a);b["observed_motion_after_red_ceased"]=False
  p=self.write("first.json",a);q=self.write("second.json",b)
  self.assertTrue(audit([p,q],"red_cessation_restart")["comparison_complete"])
  b["observed_stop_during_red"]=False;self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"held condition"):audit([p,q],"red_cessation_restart")
if __name__=="__main__":unittest.main()
