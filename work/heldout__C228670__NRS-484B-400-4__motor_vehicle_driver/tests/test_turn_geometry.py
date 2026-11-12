from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,H/(n+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load("turn_geometry").measure
audit=load("turn_comparison_audit").audit
class GeometryTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.p=Path(t.name)
  self.g={"source_directionality":"one_way","destination_directionality":"two_directional","maneuver":"left_turn","intersection_id":"junction-1","map_source":"original-map-readback","source_left_curb":[[0,0],[0,10]],"destination_centerline":[[0,0],[10,0]]}
  self.b={"subject_id":"ego","frames":[{"frame":0,"subject_id":"ego","phase":"approach","ground_corners":[[.5,1],[1,1],[1,2],[.5,2]]},{"frame":1,"subject_id":"ego","phase":"leaving_intersection","ground_corners":[[1,-1],[2,-1],[2,-2],[1,-2]]}]}
 def write(self,n,o):
  p=self.p/n;p.write_text(json.dumps(o));return p
 def measure(self):return measure(self.write("geometry.json",self.g),self.write("body.json",self.b))
 def test_original_corners_and_right_side(self):
  r=self.measure();self.assertTrue(r["departure_all_corners_right_of_centerline"]);self.assertEqual(r["approach_left_curb_nearest_m"],.5)
  self.assertIsNone(r["legal_conclusion"])
 def test_wrong_directionality_and_missing_phases_rejected(self):
  self.g["source_directionality"]="two_directional"
  with self.assertRaisesRegex(ValueError,"layout"):self.measure()
  self.g["source_directionality"]="one_way";self.b["frames"][1]["phase"]="approach"
  with self.assertRaisesRegex(ValueError,"phases"):self.measure()
 def test_approach_comparison_and_held_departure(self):
  first=self.measure();self.b["frames"][0]["ground_corners"]=[[1.5,1],[2,1],[2,2],[1.5,2]]
  second=self.measure();p1=self.write("first.json",first);p2=self.write("second.json",second)
  self.assertTrue(audit([p1,p2],"approach_curb_position")["comparison_complete"])
  second["departure_all_corners_right_of_centerline"]=False;self.write("second.json",second)
  with self.assertRaisesRegex(ValueError,"held departure"):audit([p1,p2],"approach_curb_position")
  second["departure_all_corners_right_of_centerline"]=True
  second["departure_centerline_min_signed_m"]+=.5;self.write("second.json",second)
  with self.assertRaisesRegex(ValueError,"held departure"):audit([p1,p2],"approach_curb_position")
  second["departure_centerline_min_signed_m"]-=.5
  second["geometry_sha256"]="changed";self.write("second.json",second)
  with self.assertRaisesRegex(ValueError,"fixed geometry"):audit([p1,p2],"approach_curb_position")
 def test_departure_comparison_and_held_approach(self):
  first=self.measure();self.b["frames"][1]["ground_corners"]=[[1,1],[2,1],[2,2],[1,2]]
  second=self.measure();p1=self.write("first.json",first);p2=self.write("second.json",second)
  self.assertTrue(audit([p1,p2],"departure_centerline_side")["comparison_complete"])
  second["approach_left_curb_nearest_m"]=9;self.write("second.json",second)
  with self.assertRaisesRegex(ValueError,"held approach"):audit([p1,p2],"departure_centerline_side")
if __name__=="__main__":unittest.main()
