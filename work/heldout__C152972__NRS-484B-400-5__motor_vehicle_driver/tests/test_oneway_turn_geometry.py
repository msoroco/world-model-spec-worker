from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,H/(n+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load("oneway_turn_geometry").measure
audit=load("oneway_turn_comparison_audit").audit
class OnewayTurnTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.p=Path(t.name)
  self.g={"source_directionality":"one_way","destination_directionality":"one_way","maneuver":"left_turn","intersection_id":"junction-1","map_source":"original-map-readback","source_left_curb":[[0,0],[0,10]],"destination_left_curb":[[0,0],[10,0]]}
  self.b={"subject_id":"ego","frames":[{"frame":0,"subject_id":"ego","phase":"approach","ground_corners":[[.5,1],[1,1],[1,2],[.5,2]]},{"frame":1,"subject_id":"ego","phase":"leaving_intersection","ground_corners":[[1,-.5],[2,-.5],[2,-1],[1,-1]]}]}
 def write(self,n,o):
  p=self.p/n;p.write_text(json.dumps(o));return p
 def measure(self):return measure(self.write("geometry.json",self.g),self.write("body.json",self.b))
 def test_both_curb_distances_from_original_corners(self):
  r=self.measure();self.assertEqual(r["approach_left_curb_nearest_m"],.5)
  self.assertEqual(r["departure_left_curb_nearest_m"],.5)
  self.assertIsNone(r["legal_conclusion"])
 def test_wrong_directionality_and_phase_rejected(self):
  self.g["destination_directionality"]="two_directional"
  with self.assertRaisesRegex(ValueError,"layout"):self.measure()
  self.g["destination_directionality"]="one_way";self.b["frames"][1]["phase"]="approach"
  with self.assertRaisesRegex(ValueError,"phases"):self.measure()
 def test_approach_and_departure_comparisons(self):
  a=self.measure();self.b["frames"][0]["ground_corners"]=[[1.5,1],[2,1],[2,2],[1.5,2]]
  b=self.measure();p=self.write("first.json",a);q=self.write("second.json",b)
  self.assertTrue(audit([p,q],"approach_curb_position")["comparison_complete"])
  b["departure_left_curb_nearest_m"]=5;self.write("second.json",b)
  with self.assertRaisesRegex(ValueError,"held curb"):audit([p,q],"approach_curb_position")
  self.b["frames"][0]["ground_corners"]=[[.5,1],[1,1],[1,2],[.5,2]]
  self.b["frames"][1]["ground_corners"]=[[1,-1.5],[2,-1.5],[2,-2],[1,-2]]
  b=self.measure();self.write("second.json",b)
  self.assertTrue(audit([p,q],"turn_departure_curb_position")["comparison_complete"])
if __name__=="__main__":unittest.main()
