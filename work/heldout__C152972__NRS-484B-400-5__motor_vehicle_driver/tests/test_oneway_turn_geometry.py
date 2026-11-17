from __future__ import annotations
import hashlib,importlib.util,json,tempfile,unittest
from types import SimpleNamespace
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,H/(n+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
measure=load("oneway_turn_geometry").measure
construct_route_targets=load("oneway_turn_geometry").construct_route_targets
finalize_original_sources=load("oneway_turn_geometry").finalize_original_sources
audit=load("oneway_turn_geometry").audit
native_route_plan=load("oneway_turn_geometry").native_route_plan
spawn_native_scene=load("oneway_turn_geometry").spawn_native_scene
spawn_native_cameras=load("oneway_turn_geometry").spawn_native_cameras
apply_route_control=load("oneway_turn_geometry").apply_route_control
native_result=load("oneway_turn_geometry").native_result
finalize_and_write=load("oneway_turn_geometry").finalize_and_write
NativeCameraFrameJoin=load("oneway_turn_geometry").NativeCameraFrameJoin
OriginalCurbBodyCapture=load("oneway_turn_geometry").OriginalCurbBodyCapture
seal_curb_sources=load("oneway_turn_geometry").seal_curb_sources
check_native_config=load("oneway_turn_geometry").check_native_config
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
 def test_nonfinite_original_geometry_rejected(self):
  self.g["source_left_curb"][0][0]=float("nan")
  with self.assertRaisesRegex(ValueError,"invalid map point"):self.measure()
  self.g["source_left_curb"][0][0]=0
  self.b["frames"][0]["ground_corners"][0][0]=float("inf")
  with self.assertRaisesRegex(ValueError,"four original ground body corners"):self.measure()
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
  receipt=seal_curb_sources(self.p,"near-near",require_decodable_media=False)
  self.assertFalse(receipt["four_camera_decode_checked"])
  channels=[{"name":name,"unit":"m" if name.endswith("_m") else "categorical"} for name in ("approach_left_curb_nearest_m","departure_left_curb_nearest_m","original_turn_phase","original_one_way_context","original_left_curb_geometry")]
  self.write("config.json",{"selected_case_id":"near-near","curb_offsets_m":{"approach":.5,"departure":.5},"case":{"recording_description":{"channels":channels}}})
  result=finalize_and_write(self.p,self.p/"curb-analysis.json")
  report=json.loads((self.p/"curb-analysis.json").read_text())
  self.assertEqual(report["measurement"]["approach_left_curb_nearest_m"],.5)
  self.assertEqual(report["measurement"]["departure_left_curb_nearest_m"],.5)
  self.assertEqual(len(report["recording_evidence"]),5)
  self.assertFalse(report["physical_acceptance_claimed"])
  self.assertEqual(json.loads((self.p/"result.json").read_text()),result)
  self.assertFalse(result["maneuver_completed"])
  self.assertEqual(result["realized_observables"]["approach_left_curb_nearest_m"]["value"],.5)
  self.assertEqual(len(result["recording_evidence"]),5)
  with self.assertRaisesRegex(ValueError,"retain prior curb analysis"):finalize_and_write(self.p,self.p/"curb-analysis.json")
  self.p.joinpath("approach_left_curb_nearest_m.jsonl").write_text("{}\n")
  with self.assertRaisesRegex(ValueError,"derived stream changed"):native_result(self.p,report)
  self.p.joinpath("approach_left_curb_nearest_m.jsonl").unlink()
  self.p.joinpath("body_ground_original.json").write_text(self.p.joinpath("body_ground_original.json").read_text()+" ")
  with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
   finalize_original_sources(self.p)
 def test_original_body_capture_uses_native_road_and_ground_readback(self):
  self.g.update(source_road_id=11,destination_road_id=22)
  source=self.write("source-map.json",self.g)
  class Ego:
   def __init__(self):
    self.bounding_box=SimpleNamespace(get_world_vertices=lambda transform:[SimpleNamespace(x=x,y=y,z=z) for z in (0,2) for x,y in ((0,0),(1,0),(1,1),(0,1))])
   def get_transform(self):return SimpleNamespace(location=SimpleNamespace(x=0,y=0))
  class World:
   def __init__(self):self.frame=10;self.road=11
   def get_map(self):return SimpleNamespace(name="original-map-readback",get_waypoint=lambda location:SimpleNamespace(road_id=self.road,is_junction=False))
   def get_snapshot(self):return SimpleNamespace(frame=self.frame)
  world=World();ego=Ego();scene={"ego":ego}
  pipeline=SimpleNamespace(capture=lambda frame,time_s:{"frame":frame,"time_s":time_s})
  cameras=SimpleNamespace(capture_frame=lambda frame,time_s:None)
  capture=OriginalCurbBodyCapture(self.p,world,scene,source,pipeline)
  first=capture.capture(10,0,cameras)
  self.assertEqual(first["phase"],"approach")
  world.frame=11;world.road=22
  second=capture.capture(11,.05,cameras)
  self.assertEqual(second["phase"],"leaving_intersection")
  capture.close()
  body=json.loads((self.p/"body_ground_original.json").read_text())
  self.assertEqual(len(body["frames"]),2)
  self.assertEqual(len(body["frames"][0]["ground_corners"]),4)
  self.assertEqual(len((self.p/"video_frames.jsonl").read_text().splitlines()),2)
  with self.assertRaisesRegex(ValueError,"capture closed"):capture.capture(11,.05,cameras)
 def test_native_route_and_four_camera_creation(self):
  self.g.update(source_left_curb_inward_unit=[1,0],destination_left_curb_inward_unit=[0,-1],source_road_width_m=4,destination_road_width_m=4,source_travel_unit=[0,1],destination_travel_unit=[1,0])
  route_path=self.write("native-map.json",self.g)
  a=native_route_plan(route_path,"approach_near_depart_near")
  b=native_route_plan(route_path,"approach_far_depart_near")
  c=native_route_plan(route_path,"approach_near_depart_far")
  self.assertEqual(a["departure"],b["departure"])
  self.assertEqual(a["approach"],c["approach"])
  self.assertEqual(a["source_heading_deg"],90)
  config={"case_branch":"approach_near_depart_near","selected_case_id":"heldout__C152972__NRS-484B-400-5__motor_vehicle_driver__approach_near_depart_near","law_id":"NRS-484B-400-5","cell_id":"C152972","frames":160,"duration_s":8,"source_geometry_sha256":a["geometry_sha256"],"curb_offsets_m":{"approach":.5,"departure":.5},"vehicle_blueprint_id":"vehicle.test"}
  self.assertEqual(check_native_config(config,route_path)["branch"],config["case_branch"])
  config["source_geometry_sha256"]="bad"
  with self.assertRaisesRegex(ValueError,"hash differs"):check_native_config(config,route_path)
  config["source_geometry_sha256"]=a["geometry_sha256"]
  class BP:
   def __init__(self):self.attributes={}
   def set_attribute(self,k,v):self.attributes[k]=v
  class Actor:
   def __init__(self):self.sink=None;self.destroyed=False
   def listen(self,sink):self.sink=sink
   def stop(self):self.stopped=True
   def destroy(self):self.destroyed=True
  class World:
   def __init__(self):self.map_name="original-map-readback";self.spawned=[];self.blueprints=[]
   def get_map(self):return SimpleNamespace(name=self.map_name)
   def get_blueprint_library(self):return SimpleNamespace(find=self.find)
   def find(self,name):
    bp=BP();self.blueprints.append((name,bp));return bp
   def try_spawn_actor(self,bp,transform):
    self.spawned.append((bp,transform));return Actor()
   def spawn_actor(self,bp,transform,attach_to):
    self.spawned.append((bp,transform,attach_to));return Actor()
  carla=SimpleNamespace(Location=lambda *a,**k:(a,k),Rotation=lambda *a,**k:(a,k),Transform=lambda l,r:(l,r))
  world=World();scene=spawn_native_scene(world,carla,route_path,"approach_near_depart_near","vehicle.test")
  self.assertEqual(len(scene["actors"]),1)
  sinks={name:(lambda image:None) for name in ("overview","approach","reference_corner","driver_reference")}
  spawn_native_cameras(world,carla,scene,sinks)
  self.assertEqual(set(scene["camera_actors"]),set(sinks))
  self.assertEqual(len(scene["actors"]),5)
  self.assertTrue(all(bp.attributes.get("image_size_x")=="960" for name,bp in world.blueprints if name=="sensor.camera.rgb"))
  with self.assertRaisesRegex(ValueError,"already attached"):spawn_native_cameras(world,carla,scene,sinks)
  world.map_name="different-map"
  with self.assertRaisesRegex(ValueError,"map differs"):spawn_native_scene(world,carla,route_path,"approach_near_depart_near","vehicle.test")
  self.g["destination_travel_unit"]=[-1,0]
  with self.assertRaisesRegex(ValueError,"heading disagrees"):native_route_plan(self.write("reverse.json",self.g),"approach_near_depart_near")
  class FakeSink:
   def __init__(self,root,name):self.frames=[];self.closed=False
   def write(self,image):self.frames.append(image.frame)
   def close(self):self.closed=True
  world=World();scene=spawn_native_scene(world,carla,route_path,"approach_near_depart_near","vehicle.test")
  join=NativeCameraFrameJoin(self.p,world,carla,scene,sink_factory=FakeSink)
  for sensor in scene["camera_actors"].values():sensor.sink(SimpleNamespace(frame=100))
  self.assertEqual(join.capture_frame(100,0),{"video_frame":0,"native_frame":100,"time_s":0})
  for name in scene["camera_actors"]:
   self.assertEqual(json.loads((self.p/(name+"-frames.jsonl")).read_text()),{"video_frame":0,"native_frame":100,"time_s":0})
  scene["camera_actors"]["overview"].sink(SimpleNamespace(frame=100))
  with self.assertRaisesRegex(ValueError,"callback failed"):join.capture_frame(101,.05,timeout_s=.01)
  join.close()
  self.assertTrue(all(sink.closed for sink in join.sinks.values()))
 def test_route_controller_reads_native_pose_and_steers_both_sides(self):
  class Ego:
   def __init__(self,x,y,yaw):self.pose=SimpleNamespace(location=SimpleNamespace(x=x,y=y),rotation=SimpleNamespace(yaw=yaw));self.control=None
   def get_transform(self):return self.pose
   def get_velocity(self):return SimpleNamespace(x=0.,y=0.)
   def apply_control(self,control):self.control=control
  carla=SimpleNamespace(VehicleControl=lambda **k:k)
  ego=Ego(0,0,0)
  scene={"ego":ego,"route":{"route_xy_m":[[2,0],[2,2],[0,2]]}}
  straight=apply_route_control(scene,carla,0)
  self.assertAlmostEqual(ego.control["steer"],0)
  self.assertGreater(ego.control["throttle"],0)
  left=apply_route_control(scene,carla,1)
  self.assertGreater(ego.control["steer"],0)
  right=apply_route_control(scene,carla,2)
  self.assertGreater(ego.control["steer"],0)
  ego.pose.rotation.yaw=180
  opposite=apply_route_control(scene,carla,1)
  self.assertLess(ego.control["steer"],0)
  self.assertFalse(straight["reached"])
  self.assertEqual(opposite["waypoint_index"],1)
  with self.assertRaisesRegex(ValueError,"waypoint missing"):apply_route_control(scene,carla,3)
if __name__=="__main__":unittest.main()
