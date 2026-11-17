from __future__ import annotations
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,H/(n+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load("oneway_turn_geometry").measure
construct_route_targets=load("oneway_turn_geometry").construct_route_targets
finalize_original_sources=load("oneway_turn_geometry").finalize_original_sources
audit=load("oneway_turn_geometry").audit
class OnewayTurnTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.p=Path(t.name)
  self.serial=0
  self.g={"source_directionality":"one_way","destination_directionality":"one_way","maneuver":"left_turn","intersection_id":"junction-1","map_source":"original-map-readback","source_left_curb":[[0,0],[0,10]],"destination_left_curb":[[0,0],[10,0]]}
  self.b={"subject_id":"ego","frames":[{"frame":0,"subject_id":"ego","phase":"approach","ground_corners":[[.5,1],[1,1],[1,2],[.5,2]]},{"frame":1,"subject_id":"ego","phase":"leaving_intersection","ground_corners":[[1,-.5],[2,-.5],[2,-1],[1,-1]]}]}
 def write(self,n,o):
  p=self.p/n;p.write_text(json.dumps(o));return p
 def measure(self):
  self.serial+=1
  return measure(self.write(f"geometry-{self.serial}.json",self.g),self.write(f"body-{self.serial}.json",self.b))
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
 def test_comparison_rejects_changed_or_missing_original(self):
  first=self.measure()
  self.b["frames"][0]["ground_corners"]=[[1.5,1],[2,1],[2,2],[1.5,2]]
  second=self.measure()
  p=self.write("first.json",first);q=self.write("second.json",second)
  self.assertTrue(audit([p,q],"approach_curb_position")["comparison_complete"])
  source=Path(second["source_refs"][1]);source.write_text(source.read_text()+" ")
  with self.assertRaisesRegex(ValueError,"changed original source"):audit([p,q],"approach_curb_position")
  source.unlink()
  with self.assertRaisesRegex(ValueError,"missing or changed original source"):audit([p,q],"approach_curb_position")
 def test_source_bound_independent_route_targets(self):
  self.g.update(source_left_curb_inward_unit=[1,0],destination_left_curb_inward_unit=[0,-1],source_road_width_m=4,destination_road_width_m=4)
  p=self.write("map.json",self.g)
  near=construct_route_targets(p,.5,.5)
  approach_far=construct_route_targets(p,1.5,.5)
  departure_far=construct_route_targets(p,.5,1.5)
  self.assertEqual(near["departure"],approach_far["departure"])
  self.assertEqual(near["approach"],departure_far["approach"])
  self.assertEqual(approach_far["approach"]["waypoints_xy_m"][0][0],1.5)
  self.assertEqual(departure_far["departure"]["waypoints_xy_m"][0][1],-1.5)
  self.assertFalse(near["actual_native_motion_verified"])
  self.assertIsNone(near["legal_conclusion"])
  self.g["destination_left_curb_inward_unit"]=[1,0]
  with self.assertRaisesRegex(ValueError,"normal"):construct_route_targets(self.write("bad-map.json",self.g),.5,.5)
  self.g["destination_left_curb_inward_unit"]=[0,-1]
  with self.assertRaisesRegex(ValueError,"width"):construct_route_targets(self.write("good-map.json",self.g),.5,5)
 def test_four_camera_original_join_and_tamper_rejection(self):
  self.b["frames"][0]["time_s"]=0.0
  self.b["frames"][1]["time_s"]=.05
  self.write("oneway_geometry_original.json",self.g)
  self.write("body_ground_original.json",self.b)
  for name in ("trace.jsonl","video_frames.jsonl"):
   self.p.joinpath(name).write_text("".join(json.dumps({"frame":i,"native_frame":i,"video_frame":i,"time_s":i*.05})+"\n" for i in range(2)))
  for camera in ("overview","approach","reference_corner","driver_reference"):
   self.p.joinpath(camera+".mkv").write_bytes(b"diagnostic-only-video-source")
   self.p.joinpath(camera+"-frames.jsonl").write_text("".join(json.dumps({"native_frame":i,"time_s":i*.05})+"\n" for i in range(2)))
  sources=[p for p in self.p.iterdir() if p.name!="curb_source_receipt.json"]
  receipt={"case_id":"near-near","source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
  self.write("curb_source_receipt.json",receipt)
  report=finalize_original_sources(self.p)
  self.assertEqual(report["measurement"]["approach_left_curb_nearest_m"],.5)
  self.assertEqual(report["measurement"]["departure_left_curb_nearest_m"],.5)
  self.assertEqual(len(report["recording_evidence"]),5)
  self.assertFalse(report["physical_acceptance_claimed"])
  self.p.joinpath("approach_left_curb_nearest_m.jsonl").unlink()
  self.p.joinpath("body_ground_original.json").write_text(self.p.joinpath("body_ground_original.json").read_text()+" ")
  with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
   finalize_original_sources(self.p)
if __name__=="__main__":unittest.main()
