import importlib.util
import copy
import subprocess
import sys
import json
import tempfile
import unittest
import hashlib
from pathlib import Path
from queue import Queue
from shapely.geometry import Polygon
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("blind_signal_measurements")
construction = load("occluder_construction")
signals = load("signal_control")
site = load("blind_site")
routes = load("interaction_routes")
sources = load("three_vehicle_sources")
cameras = load("source_cameras")
control = load("vehicle_control")
sys.path.insert(0,str(ROOT))
runner = load("native_runner")
entrypoint = load("runner")
finalizer = load("saved_finalizer")


def vehicle(x, speed, signed):
    return {"intersection_id": 44, "speed_mps": speed,
            "front_to_stop_line_signed_m": signed,
            "body_vertices_xy_m": [[x+dx, y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]}


class BlindSignalTests(unittest.TestCase):
    def test_draft_package_config_binds_all_cases_cameras_and_source_terms(self):
        config=json.loads((ROOT/"config.json").read_text())
        plan=json.loads((ROOT/"case-plan.json").read_text())
        self.assertIn(config["selected_case_id"],
                      {case["case_id"] for case in plan["cases"]})
        self.assertEqual(set(config["supported_case_ids"]),
                         {case["case_id"] for case in plan["cases"]})
        proposal=json.loads((ROOT/"proposals/cases.json").read_text())
        self.assertEqual({case["case_id"] for case in proposal["cases"]},
                         set(config["supported_case_ids"]))
        self.assertEqual(proposal["status"],"draft")
        self.assertEqual(config["frames"],config["duration_s"]*config["rate_hz"])
        self.assertEqual([camera["name"] for camera in config["cameras"]],
                         list(cameras.CAMERAS))
        self.assertEqual(plan["camera_plan"]["profile"],"overview1080-capability")
        declared={item["name"] for item in
                  config["recording_description"]["channels"]}
        self.assertEqual({item["name"] for item in plan["observations"]},declared)
        for mapping in plan["source_observation_mapping"].values():
            self.assertTrue(set(mapping["channels"]) <= declared)
            self.assertTrue(mapping["source_refs"])
        self.assertEqual(config["occluder"]["blueprint_filter"],"vehicle.*")
        self.assertEqual(config["occluder"]["placement"],
                         {"x":-12,"y":-12,"z":0.5,"yaw":45})
        self.assertEqual(entrypoint.validate_config()["selected_case_id"],
                         config["selected_case_id"])

    def test_saved_only_source_preflight_joins_trace_and_four_videos(self):
        case="testing__C24811__NRS-484B-250-4__motor_vehicle_driver__off_stop_earlier_and_occupied"
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            (root/"config.json").write_text(json.dumps({"cell_id":"C24811",
                "law_id":"NRS-484B-250-4","selected_case_id":case}))
            mapping=[json.loads(line) for line in (root/"video_frames.jsonl").read_text().splitlines()]
            (root/"trace.jsonl").write_text("".join(json.dumps({"frame":m["carla_frame"],
                "time_s":m["time_s"]})+"\n" for m in mapping))
            (root/"capture").mkdir()
            (root/"capture/evidence.jsonl").write_text("{}\n")
            (root/"capture/manifest.json").write_text(json.dumps({"case_id":case,
                "acquisition":"synthetic_fixture","extraction_confirmed":True,
                "frames":len(mapping)}))
            for name in cameras.CAMERAS:
                with cameras.ffv1_writer(root/(name+".mkv"),(4,4)) as write:
                    for _ in mapping:
                        write(bytes([0,0,0,255])*16)
            sealed={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                    for name in finalizer.REQUIRED if name!="capture-seal.json"}
            (root/"capture-seal.json").write_text(json.dumps({
                "provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
                "frames":len(mapping),
                "restoration":{"restored":True},"physical_acceptance_claimed":False,
                "encoder_exit_codes":{name:0 for name in cameras.CAMERAS},
                "sources":sealed}))
            proof=finalizer.validate_sources(root)
            self.assertEqual(proof["camera_frame_counts"],{name:4 for name in cameras.CAMERAS})
            self.assertEqual(proof["provenance_kind"],"synthetic_fixture")
            (root/"capture/evidence.jsonl").write_text("{\"changed\":true}\n")
            with self.assertRaisesRegex(ValueError,"Sealed original source changed"):
                finalizer.validate_sources(root)
            (root/"capture/evidence.jsonl").write_text("{}\n")
            (root/"driver_reference.mkv").unlink()
            with self.assertRaisesRegex(ValueError,"driver_reference"):
                finalizer.validate_sources(root)

    def test_native_runner_cpu_plan_and_latched_three_body_feedback(self):
        proof=runner.check()
        self.assertEqual(proof["routes"]["case_count"],5)
        self.assertFalse(proof["native_capture_verified"])
        region=Polygon([[-8,-8],[8,-8],[8,8],[-8,8]])
        entered={role:False for role in ("ego","earlier","occupant")}
        cleared=dict(entered)
        previous={"observed_ego_halt":False,"observed_earlier_halt":False,
                  "observed_occupant_halt":False}
        def row(earlier_y,occupant_y,speed):
            def body(x,y):
                return [[x-1,y-1],[x-1,y+1],[x+1,y+1],[x+1,y-1]]
            return {role:{"speed_mps":speed,"front_to_stop_line_signed_m":0.2,
                          "body_vertices_xy_m":body(*point)} for role,point in
                    (("ego",(-20,-1.8)),("earlier",(1.8,earlier_y)),
                     ("occupant",(1.8,occupant_y)))}
        first=runner._feedback(row(-20,-40,0),entered,cleared,region,previous)
        self.assertTrue(first["observed_earlier_halt"])
        second=runner._feedback(row(0,-30,3),entered,cleared,region,first)
        third=runner._feedback(row(20,0,3),entered,cleared,region,second)
        self.assertTrue(third["observed_earlier_halt"])
        self.assertTrue(third["observed_earlier_clearance"])
        self.assertTrue(third["observed_occupant_entry"])

    def test_native_stop_and_rolling_commands_use_speed_feedback(self):
        commands=[]
        actor=NS(get_velocity=lambda:NS(x=0,y=0,z=0),
                 apply_control=lambda command:commands.append(command))
        carla=NS(VehicleControl=lambda:NS(steer=0,throttle=0,brake=0))
        stopped=control.StopController(release_frame=10,target_speed_mps=3)
        held=stopped.step(carla,actor,1,0.2,release_condition=False)
        self.assertEqual(held["full_halt_frame"],1)
        self.assertTrue(held["held"])
        self.assertEqual(commands[-1].brake,1)
        released=stopped.step(carla,actor,11,0.2,release_condition=True)
        self.assertFalse(released["held"])
        self.assertGreater(commands[-1].throttle,0)
        fresh=control.StopController(release_frame=0,target_speed_mps=3)
        with self.assertRaisesRegex(ValueError,"without measured full halt"):
            fresh.step(carla,actor,0,-0.1)
        rolling=control.RollingController(target_speed_mps=3)
        command=rolling.step(carla,actor,0,1.0)
        self.assertTrue(command["rolling_comparison"])
        self.assertGreater(commands[-1].throttle,0)

    def test_four_source_camera_profile_and_exact_native_frame_join(self):
        proof=cameras.validate_plan(ROOT/"capture-plan.json")
        self.assertEqual(proof["names"],list(cameras.CAMERAS))
        self.assertEqual(proof["frames_planned"],900)
        queue=Queue()
        queue.put(NS(frame=11,raw_data=b"stale"))
        queue.put(NS(frame=12,raw_data=b"source"))
        self.assertEqual(cameras.source_camera_frame(queue,12),b"source")
        queue.put(NS(frame=14,raw_data=b"skipped"))
        with self.assertRaisesRegex(ValueError,"skipped"):
            cameras.source_camera_frame(queue,13)

    def test_ffv1_writer_produces_decodable_original_frame_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"source.mkv"
            with cameras.ffv1_writer(path,(4,4)) as write:
                write(bytes([0,0,0,255])*16)
                write(bytes([255,0,0,255])*16)
            probe=subprocess.run(["ffprobe","-v","error","-count_frames",
                "-select_streams","v:0","-show_entries","stream=codec_name,nb_read_frames",
                "-of","json",str(path)],capture_output=True,text=True,check=True)
            stream=json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"],"ffv1")
            self.assertEqual(stream["nb_read_frames"],"2")

    def test_three_vehicle_native_source_row_retains_complete_bodies_and_head_states(self):
        plan=json.loads((ROOT/"interaction-routes.json").read_text())
        def actor(identifier,x,y):
            vertices=[NS(x=x+dx,y=y+dy) for dx,dy in
                      ((-1,-1),(-1,1),(1,1),(1,-1))]
            return NS(id=identifier,get_transform=lambda:None,
                      get_velocity=lambda:NS(x=3,y=0,z=0),
                      bounding_box=NS(get_world_vertices=lambda transform:vertices))
        actors={"ego":actor(41,-20,-1.8),"earlier":actor(42,1.8,-25),
                "occupant":actor(43,1.8,-50)}
        lights=[NS(id=17,get_state=lambda:"TrafficLightState.Off"),
                NS(id=18,get_state=lambda:"TrafficLightState.Off")]
        row=sources.source_row(100,5.0,158191,lights,actors,plan["vehicles"])
        self.assertEqual(row["signal_states"],{"17":"Off","18":"Off"})
        self.assertEqual(row["actor_ids"],{"ego":41,"earlier":42,"occupant":43})
        self.assertEqual(len(row["occupant"]["body_vertices_xy_m"]),4)
        self.assertGreater(row["ego"]["front_to_stop_line_signed_m"],0)
        actors["occupant"].id=42
        with self.assertRaisesRegex(ValueError,"Distinct observed Native vehicle"):
            sources.source_row(101,5.05,158191,lights,actors,plan["vehicles"])

    def test_three_vehicle_routes_bind_map_and_separate_same_lane_spawns(self):
        proof=routes.validate(ROOT/"interaction-routes.json")
        self.assertEqual(proof["route_roles"],["ego","earlier","occupant"])
        self.assertEqual(proof["shared_lane_spawn_spacing_m"],32)
        self.assertFalse(proof["native_motion_verified"])

    def test_three_vehicle_routes_reject_shared_lane_overlap_and_map_tamper(self):
        original=json.loads((ROOT/"interaction-routes.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"blind-site-candidate.json").write_bytes((ROOT/"blind-site-candidate.json").read_bytes())
            (root/"blind-inoperative-stop-line.xodr").write_bytes(
                (ROOT/"blind-inoperative-stop-line.xodr").read_bytes())
            path=root/"interaction-routes.json"
            overlapping=copy.deepcopy(original)
            overlapping["vehicles"]["occupant"]["spawn_road_lane_s"][2]=45
            path.write_text(json.dumps(overlapping))
            with self.assertRaisesRegex(ValueError,"overlap"):
                routes.validate(path)
            path.write_text(json.dumps(original))
            (root/"blind-inoperative-stop-line.xodr").write_text("changed map")
            with self.assertRaisesRegex(ValueError,"map differs"):
                routes.validate(path)

    def test_release_permissions_use_measured_entry_clearance_and_separation(self):
        plan=json.loads((ROOT/"interaction-routes.json").read_text())
        obs={"observed_ego_halt":True,"observed_earlier_halt":True,
             "scheduled_frame":True,"observed_earlier_clearance":True,
             "observed_occupant_halt":True,"observed_occupant_entry":True,
             "ego_occupant_body_separation_m":5}
        self.assertTrue(routes.release_permission(plan,"off_stop_earlier_and_occupied","ego",obs))
        self.assertTrue(routes.release_permission(plan,"off_stop_earlier_and_occupied","occupant",obs))
        self.assertFalse(routes.release_permission(plan,"off_stop_earlier_only","occupant",obs))
        close=dict(obs,ego_occupant_body_separation_m=2)
        self.assertFalse(routes.release_permission(plan,"off_stop_earlier_and_occupied","ego",close))
        no_entry=dict(obs,observed_occupant_entry=False)
        self.assertFalse(routes.release_permission(plan,"off_stop_earlier_and_occupied","ego",no_entry))
        self.assertTrue(routes.release_permission(plan,"off_stop_earlier_only","ego",no_entry))
        with self.assertRaisesRegex(ValueError,"Measured body separation"):
            routes.release_permission(plan,"off_stop_earlier_and_occupied","ego",
                                      dict(obs,ego_occupant_body_separation_m=float("nan")))

    def test_authored_site_has_two_governed_marked_entrances_and_safe_blind_corner(self):
        candidate = ROOT/"blind-site-candidate.json"
        proof = site.validate(candidate)
        self.assertEqual(proof["planned_sight_ray_intersections"],
                         {"ego": True, "other": True})
        self.assertTrue(all(value >= 4 for value in
                            proof["planned_corridor_clearance_m"].values()))
        self.assertFalse(proof["native_visibility_verified"])

    def test_authored_site_rejects_clearance_and_missing_ray(self):
        original = json.loads((ROOT/"blind-site-candidate.json").read_text())
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp)/"candidate.json"
            local_map = Path(tmp)/original["map"]["path"]
            local_map.write_bytes((ROOT/original["map"]["path"]).read_bytes())
            intruding = copy.deepcopy(original)
            intruding["occluder"]["planned_footprint_xy_m"] = [
                [-14,-14],[-10,-14],[-10,0],[-14,0]]
            path.write_text(json.dumps(intruding))
            with self.assertRaisesRegex(ValueError,"vehicle corridor"):
                site.validate(path)
            missing_ray = copy.deepcopy(original)
            missing_ray["occluder"]["planned_footprint_xy_m"] = [
                [-14,10],[-10,10],[-10,14],[-14,14]]
            path.write_text(json.dumps(missing_ray))
            with self.assertRaisesRegex(ValueError,"misses sight ray"):
                site.validate(path)

    def test_all_entrance_native_off_request_and_restore(self):
        class Light:
            def __init__(self, identifier, road_id):
                self.id, self.road_id, self.state = identifier, road_id, "Green"
                self.frozen = False
            def get_affected_lane_waypoints(self):
                return [NS(road_id=self.road_id,lane_id=-1)]
            def get_state(self):
                return self.state
            def is_frozen(self):
                return self.frozen
            def set_state(self, value):
                self.state = value
            def freeze(self, value):
                self.frozen = value
        class Actors(list):
            def filter(self, pattern):
                self.pattern = pattern
                return self
        a,b=Light(17,7),Light(18,9)
        a.frozen=True
        ticks=[]
        world=NS(get_actors=lambda:Actors([a,b]),tick=lambda:ticks.append(True))
        selected=signals.find_entrance_lights(world,[(7,-1),(9,-1)])
        with signals.request_all_off(world,selected,NS(Off="Off")):
            self.assertEqual((a.get_state(),b.get_state()),("Off","Off"))
        self.assertEqual((a.get_state(),b.get_state()),("Green","Green"))
        self.assertTrue(a.frozen)
        self.assertFalse(b.frozen)
        self.assertEqual(len(ticks),2)
        with signals.request_all_state(world,selected,"Red"):
            self.assertEqual((a.get_state(),b.get_state()),("Red","Red"))
        self.assertEqual((a.get_state(),b.get_state()),("Green","Green"))
        self.assertTrue(a.frozen)

    def fixture(self, root):
        ctx = {"native_map_id":"TownX", "intersection_id":44,
               "signal_head_video_source":"front-and-overview-original",
               "all_entrances_source":"native-lane-inventory",
               "stop_line_source":"map-and-front-original",
               "occluder_geometry_source":"native-body-vertices",
               "sight_ray_source":"native-ray-samples", "stop_line_exists":True,
               "signal_heads":[{"native_id":17,"entrance_id":"west","installed":True,"uncovered":True},
                               {"native_id":18,"entrance_id":"south","installed":True,"uncovered":True}],
               "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"junction_context.json").write_text(json.dumps(ctx))
        positions = [(0,0,0),(0,0,0),(0,0,12),(12,0,12)]
        rows = []
        for i,(ego_x,earlier_x,occupant_x) in enumerate(positions):
            rows.append({"frame":100+i,"time_s":1+i*.05,
                         "signal_states":{"17":"Off","18":"Off"},
                         "ego":vehicle(ego_x,0 if i == 1 else 2,0.2 if i == 1 else -1),
                         "earlier":vehicle(earlier_x,0,0.2),
                         "occupant":vehicle(occupant_x,1,-1)})
        frames=[{"video_frame":i,"carla_frame":row["frame"],"time_s":row["time_s"]}
                for i,row in enumerate(rows)]
        (root/"vehicle_signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_three_distinct_histories_and_all_heads_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["ego_stopped_before_entry_observed"])
            self.assertTrue(result["distinct_other_stopped_earlier_observed"])
            self.assertTrue(result["distinct_occupant_inside_at_ego_entry_observed"])
            self.assertEqual(result["legal_conclusion"],"unresolved")

    def test_stationary_spawn_upstream_is_not_a_stop_line_halt(self):
        prefix="testing__C24811__NRS-484B-250-4__motor_vehicle_driver__"
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(s) for s in (root/"vehicle_signal_history.jsonl").read_text().splitlines()]
            rows[1]["ego"]["front_to_stop_line_signed_m"]=5
            (root/"vehicle_signal_history.jsonl").write_text(
                "".join(json.dumps(row)+"\n" for row in rows))
            result=measure.analyze(root)
            self.assertIsNone(result["first_full_halt"]["ego"])
            self.assertFalse(result["ego_stopped_before_entry_observed"])
            with self.assertRaisesRegex(ValueError,"do not satisfy exact case"):
                measure.analyze_exact_case(root,prefix+"off_stop_earlier_and_occupied")

    def test_exact_case_observations_reject_comparison_mismatch(self):
        prefix="testing__C24811__NRS-484B-250-4__motor_vehicle_driver__"
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze_exact_case(root,prefix+"off_stop_earlier_and_occupied")
            self.assertTrue(result["case_observations_passed"])
            for other in ("off_stop_earlier_only", "off_stop_occupant_only",
                          "off_no_full_halt"):
                with self.assertRaisesRegex(ValueError,"do not satisfy exact case"):
                    measure.analyze_exact_case(root,prefix+other)
            with self.assertRaisesRegex(ValueError,"Explicit operative indication"):
                measure.analyze_exact_case(root,prefix+"operative_signal")

    def test_operative_head_and_stale_video_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(s) for s in (root/"vehicle_signal_history.jsonl").read_text().splitlines()]
            rows[-1]["signal_states"]["18"]="Green"
            (root/"vehicle_signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"all.*Off|All governing heads"):
                measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(s) for s in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                measure.analyze(root)

    def test_operative_comparison_requires_whole_source_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(s) for s in (root/"vehicle_signal_history.jsonl").read_text().splitlines()]
            for row in rows:
                row["signal_states"]={"17":"Green","18":"Green"}
            (root/"vehicle_signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            result=measure.analyze(root,expected_signal_state="Green")
            self.assertEqual(result["expected_governing_signal_state"],"Green")
            self.assertTrue(all(not row["all_heads_off"] for row in result["samples"]))
            self.assertEqual(result["legal_conclusion"],"unresolved")
            case=measure.analyze_exact_case(
                root,"testing__C24811__NRS-484B-250-4__motor_vehicle_driver__operative_signal",
                operative_state="Green")
            self.assertTrue(case["case_observations_passed"])
            rows[-1]["signal_states"]["18"]="Off"
            (root/"vehicle_signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"Green"):
                measure.analyze(root,expected_signal_state="Green")

    def test_realized_occluder_crosses_both_approach_rays_and_cleans_up(self):
        points=[NS(x=x,y=y) for x,y in ((4,-1),(4,1),(6,1),(6,-1))]
        destroyed=[]
        actor=NS(bounding_box=NS(get_world_vertices=lambda transform:points),
                 get_transform=lambda:"transform",destroy=lambda:destroyed.append(True))
        world=NS(try_spawn_actor=lambda blueprint, transform:actor)
        rays={"ego":(NS(x=0,y=0),NS(x=10,y=0)),
              "other":(NS(x=0,y=0.5),NS(x=10,y=0.5))}
        corridors={"ego":[NS(x=0,y=3),NS(x=10,y=3)],
                   "other":[NS(x=0,y=4),NS(x=10,y=4)]}
        with construction.spawn_verified_occluder(
                world,"blueprint","spawn",rays,corridors,1.5) as realized:
            self.assertEqual(realized["approach_ray_intersections"],{"ego":True,"other":True})
            self.assertGreaterEqual(realized["vehicle_corridor_clearance_m"]["ego"],1.5)
        self.assertEqual(destroyed,[True])
        corridors["ego"]=[NS(x=0,y=1),NS(x=10,y=1)]
        with self.assertRaisesRegex(ValueError,"vehicle corridor"):
            with construction.spawn_verified_occluder(
                    world,"blueprint","spawn",rays,corridors,1.5):
                pass
        self.assertEqual(destroyed,[True,True])
        rays["other"]=(NS(x=0,y=3),NS(x=10,y=3))
        with self.assertRaisesRegex(ValueError,"both approach rays"):
            with construction.spawn_verified_occluder(world,"blueprint","spawn",rays):
                pass
        self.assertEqual(destroyed,[True,True,True])

    def test_native_occluder_candidate_selection_rejects_bad_geometry(self):
        destroyed=[]
        def actor(identifier, y):
            vertices=[NS(x=x,y=v) for x,v in ((4,y-1),(4,y+1),(6,y+1),(6,y-1))]
            return NS(bounding_box=NS(get_world_vertices=lambda transform:vertices),
                      get_transform=lambda:None,
                      destroy=lambda:destroyed.append(identifier))
        candidates=[NS(id="vehicle.b"),NS(id="vehicle.a")]
        world=NS(try_spawn_actor=lambda blueprint,transform:
                 actor(blueprint.id,5 if blueprint.id=="vehicle.a" else 0))
        rays={"ego":(NS(x=0,y=0),NS(x=10,y=0)),
              "other":(NS(x=0,y=0.5),NS(x=10,y=0.5))}
        corridors={"ego":[NS(x=0,y=3),NS(x=10,y=3)],
                   "other":[NS(x=0,y=4),NS(x=10,y=4)]}
        with construction.spawn_matching_occluder(
                world,candidates,"pose",rays,corridors,1.5) as realized:
            self.assertEqual(realized["blueprint_id"],"vehicle.b")
            self.assertEqual(realized["rejected_candidates"][0]["blueprint_id"],"vehicle.a")
            self.assertEqual(destroyed,["vehicle.a"])
        self.assertEqual(destroyed,["vehicle.a","vehicle.b"])


if __name__ == "__main__":
    unittest.main()
