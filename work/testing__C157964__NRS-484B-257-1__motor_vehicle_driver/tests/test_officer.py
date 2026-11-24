import importlib.util
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


construction=load("officer_construction")
measure=load("officer_measurements")
direction=load("officer_direction")
comparison=load("comparison_audit")
capture_sources=load("officer_capture_sources")
finalizer=load("finalizer")
camera=load("officer_camera")


def body(x):return [[x+dx,y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]


class OfficerTests(unittest.TestCase):
    def test_four_original_camera_encoder_and_packet_validation(self):
        sizes={name:(2,2) for name in camera.CAMERAS}
        packet=NS(width=2,height=2,raw_data=bytes([0,0,255,255])*4)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with camera.FourCameraEncoder(root,sizes=sizes,fps=20) as encoder:
                for _ in range(3):encoder.add_packets({name:packet for name in camera.CAMERAS})
                with self.assertRaisesRegex(ValueError,"Four original camera packets"):
                    encoder.validate_packets({"overview":packet})
                with self.assertRaisesRegex(ValueError,"Camera pixels differ"):
                    encoder.validate_packets({name:NS(width=2,height=2,raw_data=b"")
                                              for name in camera.CAMERAS})
            self.assertEqual(encoder.count,3)
            self.assertTrue(all(code==0 for code in encoder.exit_codes.values()))
            for name in camera.CAMERAS:
                probe=subprocess.run(["ffprobe","-v","error","-count_frames",
                    "-select_streams","v:0","-show_entries","stream=width,height,nb_read_frames",
                    "-of","json",str(root/(name+".mkv"))],capture_output=True,text=True,check=True)
                stream=json.loads(probe.stdout)["streams"][0]
                self.assertEqual((stream["width"],stream["height"],stream["nb_read_frames"]),(2,2,"3"))

    def saved_fixture(self,root,case_id=None):
        case_id=case_id or measure.PREFIX+"officer_active_stop_then_go"
        if case_id==measure.ABSENT:
            self.baseline_fixture(root,case_id)
        else:
            self.fixture(root)
        config={"assignment_id":finalizer.ASSIGNMENT,
                "selected_case_id":case_id,"law_id":"NRS-484B-257-1",
                "cell_id":"C157964","actor":"motor_vehicle_driver",
                "recording_description":{"channels":[{"name":"officer_control_observed"}]}}
        (root/"config.json").write_text(json.dumps(config))
        frames=[json.loads(line) for line in (root/"video_frames.jsonl").read_text().splitlines()]
        (root/"trace.jsonl").write_text("".join(json.dumps({"frame":r["carla_frame"],
             "time_s":r["time_s"],"position_m":[i*2,0]})+"\n" for i,r in enumerate(frames)))
        (root/"capture").mkdir(exist_ok=True)
        (root/"capture/evidence.jsonl").write_text("".join(json.dumps({
            "original_frame":r["carla_frame"]})+"\n" for r in frames))

    def test_saved_finalizer_uses_review_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.saved_fixture(root)
            original=(root/"officer_history.jsonl").read_bytes()
            output=root/"analysis-report.json"
            def assess(path,result):
                result["physical_checks"]={"setup":{"status":"unverified"},
                                            "target":{"status":"unverified"},
                                            "maneuver":{"status":"unverified"}}
                result["physical_acceptance_claimed"]=False
                return result
            def write(path,result):
                (path/"result.json").write_text(json.dumps(result))
            report=finalizer.finalize(root,output,physical_assessor=assess,result_writer=write)
            self.assertTrue(report["analysis_complete"])
            self.assertEqual(report["measurements"]["officer_direction_at_entry"]["value"],"go")
            self.assertEqual((root/"officer_history.jsonl").read_bytes(),original)
            result=json.loads((root/"result.json").read_text())
            self.assertTrue(all(check["matched"] for check in result["target_checks"]))
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertTrue((root/"channels/officer_context.json").is_file())
            with self.assertRaisesRegex(ValueError,"Retain previous"):
                finalizer.finalize(root,root/"second-report.json",physical_assessor=assess,result_writer=write)

    def test_saved_finalizer_rejects_missing_source_and_wrong_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.saved_fixture(root,measure.ABSENT)
            (root/"approach.mkv").unlink()
            with self.assertRaisesRegex(ValueError,"Missing required source: approach.mkv"):
                finalizer.finalize(root,root/"report.json",physical_assessor=lambda a,r:r,
                                   result_writer=lambda a,r:None)
            self.saved_fixture(root,measure.ABSENT)
            config=json.loads((root/"config.json").read_text());config["cell_id"]="C158196"
            (root/"config.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"Exact C157964"):
                finalizer.finalize(root,root/"report.json",physical_assessor=lambda a,r:r,
                                   result_writer=lambda a,r:None)

    def test_capture_writer_retains_raw_pose_and_camera_joins_without_observation_labels(self):
        class Map:
            def __init__(self,path):self.path=path;self.index=0
            def append(self,frame,time_s,**extra):
                with self.path.open("a") as stream:
                    stream.write(json.dumps({"video_frame":self.index,"carla_frame":frame,
                                             "time_s":time_s,**extra})+"\n")
                self.index+=1
            def close(self):pass
        points=[NS(x=x,y=y) for x,y in body(0)]*2
        ego=NS(bounding_box=NS(get_world_vertices=lambda transform:points),
               get_transform=lambda:NS(),get_velocity=lambda:NS(x=2.0,y=0.0,z=0.0))
        snapshot=NS(frame=101,timestamp=NS(elapsed_seconds=5.05))
        cameras={name:NS(frame=101,timestamp=5.05) for name in capture_sources.CAMERAS}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ctx={"case_id":measure.PREFIX+"officer_active_hold","officer_actor_id":25}
            pose={"frame_index":0,"officer_actor_id":25,"programmed_direction":"stop",
                  "pose_applied":True,"realized_bones":{"arm":{"pitch":90}}}
            with capture_sources.OfficerSourceWriter(root,ctx,Map) as writer:
                row=writer.add_tick(snapshot,cameras,ego,NS(id=25),pose)
            self.assertEqual(row["ego"]["speed_mps"],2.0)
            self.assertNotIn("officer_direction_observed",row)
            self.assertNotIn("traffic_control_observed",row)
            self.assertEqual(json.loads((root/"video_frames.jsonl").read_text())["camera_frames"]["overview"],101)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ctx={"case_id":measure.ABSENT,"officer_actor_id":None}
            pose={"frame_index":0,"officer_actor_id":None,"programmed_direction":"none",
                  "pose_applied":False}
            with capture_sources.OfficerSourceWriter(root,ctx,Map) as writer:
                writer.add_tick(snapshot,cameras,ego,None,pose)
            self.assertIsNone(json.loads((root/"officer_history.jsonl").read_text())["officer_actor_id"])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with capture_sources.OfficerSourceWriter(root,ctx,Map) as writer:
                invalid=dict(pose,programmed_direction="stop")
                with self.assertRaisesRegex(ValueError,"differs from exact case"):
                    writer.add_tick(snapshot,cameras,ego,None,invalid)
                stale=dict(cameras,overview=NS(frame=100,timestamp=5.05))
                with self.assertRaisesRegex(ValueError,"Stale original"):
                    writer.add_tick(snapshot,stale,ego,None,pose)

    def test_exact_direction_program_and_native_pose_readback(self):
        prefix=direction.PREFIX
        actor=NS(id=25)
        calls=[]
        def adapter(officer, command):
            calls.append((officer.id,command))
            return {"officer_actor_id":officer.id,"direction":command,
                    "realized_bones":{"right_arm":{"pitch":90 if command=="stop" else 0}}}
        stop_go=prefix+"officer_active_stop_then_go"
        self.assertEqual(direction.apply_direction(actor,adapter,stop_go,299)["programmed_direction"],"stop")
        self.assertEqual(direction.apply_direction(actor,adapter,stop_go,300)["programmed_direction"],"go")
        self.assertEqual(direction.apply_direction(actor,adapter,prefix+"officer_active_hold",599)["programmed_direction"],"stop")
        self.assertEqual(calls,[(25,"stop"),(25,"go"),(25,"stop")])
        inactive=direction.apply_direction(actor,None,prefix+"officer_present_inactive",100)
        self.assertFalse(inactive["pose_applied"])
        absent=direction.apply_direction(None,None,prefix+"no_officer_yield_nearest_view",100)
        self.assertIsNone(absent["officer_actor_id"])

    def test_direction_program_rejects_unrealized_or_wrong_actor(self):
        case=direction.PREFIX+"officer_active_hold"
        actor=NS(id=25)
        with self.assertRaisesRegex(ValueError,"adapter missing"):
            direction.apply_direction(actor,None,case,0)
        with self.assertRaisesRegex(ValueError,"readback missing"):
            direction.apply_direction(actor,lambda a,d:{"officer_actor_id":26,"direction":d,
                                                       "realized_bones":{"arm":{}}},case,0)
        with self.assertRaisesRegex(ValueError,"outside capture"):
            direction.apply_direction(actor,None,case,600)
        with self.assertRaisesRegex(ValueError,"Unknown exact"):
            direction.phases("other__officer_active_hold")
        with self.assertRaisesRegex(ValueError,"contains an officer"):
            direction.apply_direction(actor,None,direction.PREFIX+"no_officer_yield_nearest_view",0)

    def test_native_bone_adapter_applies_and_reads_back_arm_pose(self):
        stop={"arm_right":{"pitch":90,"yaw":0,"roll":0}}
        go={"arm_right":{"pitch":0,"yaw":90,"roll":0}}
        class Actor:
            id=25
            current=NS(pitch=0,yaw=0,roll=0)
            def get_bones(self):
                return NS(bone_transforms=[NS(name="arm_right",relative=NS(rotation=self.current))])
            def set_bones(self, control):self.current=control[0][1].rotation
            def blend_pose(self, weight):self.weight=weight
        carla=NS(Rotation=lambda **angles:NS(**angles),
                 Transform=lambda rotation:NS(rotation=rotation),
                 WalkerBoneControl=lambda updates:updates)
        adapter=direction.native_bone_adapter(carla,stop,go)
        actor=Actor()
        applied=direction.apply_direction(actor,adapter,direction.PREFIX+"officer_active_stop_then_go",0)
        self.assertEqual(applied["realized_bones"]["arm_right"]["pitch"],90)
        self.assertEqual(actor.weight,1.0)
        actor.get_bones=lambda:NS(bone_transforms=[("arm_right","root",NS(rotation=actor.current))])
        tuple_applied=direction.apply_direction(actor,adapter,direction.PREFIX+"officer_active_stop_then_go",300)
        self.assertEqual(tuple_applied["realized_bones"]["arm_right"]["yaw"],90)
        actor.get_bones=lambda:NS(bone_transforms=[])
        with self.assertRaisesRegex(ValueError,"lacks officer arm bones"):
            direction.apply_direction(actor,adapter,direction.PREFIX+"officer_active_hold",0)

    def fixture(self,root,active=True):
        ctx={"case_id":measure.PREFIX+"officer_active_stop_then_go",
             "native_map_id":"TownX","intersection_id":44,"officer_actor_id":25,
             "authority_source":"reviewed-operator-roster","uniform_video_source":"detail-original",
             "direction_video_source":"front-original","junction_source":"native-polygon",
             "ego_route_source":"native-waypoints",
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"officer_context.json").write_text(json.dumps(ctx))
        rows=[]
        directions=("stop","go","go")
        for i,x in enumerate((0,0,12)):
            rows.append({"frame":100+i,"time_s":1+i*.05,"officer_actor_id":25,
                         "programmed_direction":directions[i],
                         "ego":{"speed_mps":0 if i<2 else 2,"body_vertices_xy_m":body(x)}})
        cameras=("overview","approach","reference_corner","driver_reference")
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"],
                 "camera_frames":{name:r["frame"] for name in cameras}} for i,r in enumerate(rows)]
        (root/"officer_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
        camera_hashes={}
        for camera in cameras:
            source=root/(camera+".mkv")
            source.write_bytes(("synthetic diagnostic "+camera).encode())
            camera_hashes[camera]=hashlib.sha256(source.read_bytes()).hexdigest()
        review={"officer_history_sha256":hashlib.sha256((root/"officer_history.jsonl").read_bytes()).hexdigest(),
                "video_frames_sha256":hashlib.sha256((root/"video_frames.jsonl").read_bytes()).hexdigest(),
                "camera_sha256":camera_hashes,
                "frames":[{"frame":r["frame"],"video_frame":i,
                           "observed_direction":directions[i],
                           "traffic_control_observed":active,
                           "direction_frame_source":"front-original",
                           "officer_visible":True} for i,r in enumerate(rows)]}
        (root/"officer_review.json").write_text(json.dumps(review))

    def baseline_fixture(self,root,case_id):
        self.fixture(root,False)
        ctx=json.loads((root/"officer_context.json").read_text())
        ctx["case_id"]=case_id
        absent=case_id==measure.ABSENT
        if absent:
            for key in ("officer_actor_id","authority_source","uniform_video_source"):
                ctx[key]=None
        (root/"officer_context.json").write_text(json.dumps(ctx))
        rows=[json.loads(line) for line in (root/"officer_history.jsonl").read_text().splitlines()]
        for row in rows:
            row["officer_actor_id"]=None if absent else 25
            row["programmed_direction"]="none"
        (root/"officer_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        review=json.loads((root/"officer_review.json").read_text())
        review["officer_history_sha256"]=hashlib.sha256((root/"officer_history.jsonl").read_bytes()).hexdigest()
        for row in review["frames"]:
            row["observed_direction"]="none"
            row["traffic_control_observed"]=False
            row["direction_frame_source"]="four-original-camera-absence-review"
            row["officer_visible"]=not absent
        (root/"officer_review.json").write_text(json.dumps(review))

    def test_inactive_and_absent_officer_original_source_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.baseline_fixture(root,measure.INACTIVE)
            inactive=measure.analyze(root)
            self.assertFalse(inactive["officer_control_observed_at_entry"])
            self.assertTrue(inactive["first_ego_entry"]["officer_visible"])
            self.baseline_fixture(root,measure.ABSENT)
            absent=measure.analyze(root)
            self.assertFalse(absent["officer_control_observed_at_entry"])
            self.assertFalse(absent["first_ego_entry"]["officer_visible"])
            self.assertIn("not applicable",absent["police_authority_judgment"])

    def test_baseline_contradictions_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.baseline_fixture(root,measure.ABSENT)
            ctx=json.loads((root/"officer_context.json").read_text())
            ctx["officer_actor_id"]=25
            (root/"officer_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"must lack officer"):
                measure.analyze(root)
            self.baseline_fixture(root,measure.INACTIVE)
            review=json.loads((root/"officer_review.json").read_text())
            review["frames"][2]["officer_visible"]=False
            (root/"officer_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"Inactive officer baseline"):
                measure.analyze(root)

    def test_independent_active_inactive_comparison_and_fixed_context(self):
        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            first,second=Path(first_tmp),Path(second_tmp)
            self.fixture(first)
            self.baseline_fixture(second,measure.INACTIVE)
            result=comparison.audit("officer_exception_active",first,second)
            self.assertTrue(result["comparison_passed"])
            self.assertEqual(result["legal_conclusion"],"unresolved")
            ctx=json.loads((second/"officer_context.json").read_text())
            ctx["ego_route_source"]="different-native-route"
            (second/"officer_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"fixed intersection"):
                comparison.audit("officer_exception_active",first,second)

    def test_independent_direction_comparison_requires_original_hold(self):
        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            first,second=Path(first_tmp),Path(second_tmp)
            self.fixture(first)
            self.fixture(second)
            ctx=json.loads((second/"officer_context.json").read_text())
            ctx["case_id"]=measure.PREFIX+"officer_active_hold"
            (second/"officer_context.json").write_text(json.dumps(ctx))
            review=json.loads((second/"officer_review.json").read_text())
            for row in review["frames"]:row["observed_direction"]="stop"
            (second/"officer_review.json").write_text(json.dumps(review))
            self.assertTrue(comparison.audit("officer_direction",first,second)["comparison_passed"])
            review["frames"][2]["observed_direction"]="go"
            (second/"officer_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"direction contrast missing"):
                comparison.audit("officer_direction",first,second)

    def test_original_frame_control_at_entry_without_legal_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["officer_control_observed_at_entry"])
            self.assertEqual(result["first_ego_entry"]["frame"],102)
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,False)
            self.assertFalse(measure.analyze(root)["officer_control_observed_at_entry"])

    def test_stale_frame_and_missing_direction_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"review source hash"):measure.analyze(root)
            self.fixture(root)
            review=json.loads((root/"officer_review.json").read_text())
            review["frames"][1]["direction_frame_source"]=""
            (root/"officer_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"Missing direction video frame source"):
                measure.analyze(root)

    def test_camera_bytes_and_observed_direction_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            (root/"approach.mkv").write_bytes(b"changed diagnostic pixels")
            with self.assertRaisesRegex(ValueError,"camera bytes differ"):measure.analyze(root)
            self.fixture(root)
            review=json.loads((root/"officer_review.json").read_text())
            review["frames"][2]["frame"]=999
            (root/"officer_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"direction/frame join"):measure.analyze(root)

    def test_active_control_requires_visible_original_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            review=json.loads((root/"officer_review.json").read_text())
            review["frames"][2]["officer_visible"]=False
            (root/"officer_review.json").write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"lacks a visible direction"):
                measure.analyze(root)

    def test_real_native_performer_spawn_and_cleanup(self):
        location=NS(x=5.0,y=0.0,z=0.0)
        transform=NS(location=location)
        destroyed=[]
        actor=NS(get_location=lambda:location,destroy=lambda:destroyed.append(True))
        world=NS(try_spawn_actor=lambda blueprint,where:actor)
        with construction.spawn_officer_performer(world,"source-reviewed-blueprint",transform,NS(x=10,y=0,z=0)) as built:
            self.assertEqual(built["surveyed_distance_to_junction_m"],5)
        self.assertEqual(destroyed,[True])
        with self.assertRaisesRegex(ValueError,"placement"):
            with construction.spawn_officer_performer(world,"blueprint",NS(location=NS(x=10,y=0,z=0)),NS(x=10,y=0,z=0)):
                pass


if __name__=="__main__":unittest.main()
