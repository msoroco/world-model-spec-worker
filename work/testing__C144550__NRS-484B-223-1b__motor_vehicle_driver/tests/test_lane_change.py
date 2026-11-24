import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from enum import IntFlag
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


measure=load("lane_change_measurements")
construction=load("native_lane_construction")


def body(x,y):
    return [[x+dx,y+dy] for dx,dy in ((-.5,-.4),(-.5,.4),(.5,.4),(.5,-.4))]


class LaneChangeTests(unittest.TestCase):
    def test_canonical_construction_materializes_current_runner_and_sources(self):
        construction_doc=json.loads((ROOT/"construction.json").read_text())
        self.assertEqual(construction_doc["entrypoint"],"runner.py")
        config=json.loads((ROOT/"config.json").read_text())
        self.assertEqual(construction_doc["case_id"],config["selected_case_id"])
        self.assertEqual(construction_doc["recording_description"],config["recording_description"])
        for entry in construction_doc["files"]:
            self.assertEqual(entry["content"],(ROOT/entry["path"]).read_text())

    def test_canonical_runner_cpu_check_rejects_wrong_identity(self):
        check=subprocess.run([sys.executable,"runner.py","--check"],cwd=ROOT,
                             capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(check.stdout)["cpu_check_passed"])
        self.assertFalse(json.loads(check.stdout)["simulation_started"])
        sys.path.insert(0,str(ROOT))
        try:
            runner=load("runner")
            cfg=json.loads((ROOT/"config.json").read_text())
            runner.validate_config(cfg)
            cfg["cell_id"]="wrong"
            with self.assertRaisesRegex(ValueError,"assignment identity"):
                runner.validate_config(cfg)
            cfg["cell_id"]="C144550"
            cfg["target_speed_mps"]=4.5
            cfg["overview_along_m"]=75
            cfg["target_initial_route_distance_m"]=240
            runner.validate_config(cfg)
            cfg["target_speed_mps"]=float("nan")
            with self.assertRaisesRegex(ValueError,"construction knob"):
                runner.validate_config(cfg)
        finally:
            sys.path.remove(str(ROOT))

    def test_case_staging_uses_target_lane_distance_and_releases_actors(self):
        staged=[]
        def spawn(blueprint,transform):
            actor=NS(transform=transform,autopilot=None,destroyed=False)
            actor.set_autopilot=lambda value:setattr(actor,"autopilot",value)
            actor.destroy=lambda:setattr(actor,"destroyed",True)
            staged.append(actor)
            return actor
        world=NS(try_spawn_actor=spawn)
        target=NS(road_id=7,lane_id=-2)
        target.next=lambda distance:[NS(road_id=7,lane_id=-2,
                                         transform=NS(distance=distance))]
        site={"spawn":NS(distance=0),"selected":{"target":target,"direction":"left"}}
        prefix=construction.CASE_PREFIX
        with construction.stage_native_lane_case(
                world,site,prefix+"left_signal_before_clear_gap",object()) as actors:
            self.assertEqual(actors["target_initial_route_distance_m"],245)
            self.assertIs(actors["ego"],staged[0])
            self.assertEqual(staged[1].transform.distance,245)
        self.assertTrue(all(actor.destroyed and actor.autopilot is False for actor in staged))
        with construction.stage_native_lane_case(
                world,site,prefix+"left_signal_before_close_gap",object()) as actors:
            self.assertEqual(actors["target_initial_route_distance_m"],25)
            self.assertEqual(staged[3].transform.distance,25)
        self.assertTrue(staged[2].destroyed and staged[3].destroyed)
        with construction.stage_native_lane_case(
                world,site,prefix+"left_signal_before_clear_gap",object(),240) as actors:
            self.assertEqual(actors["target_initial_route_distance_m"],240)
        with self.assertRaisesRegex(ValueError,"direction differ"):
            with construction.stage_native_lane_case(
                    world,site,prefix+"right_signal_before_clear_gap",object()):pass
        self.assertEqual(len(staged),6)
        failures=[]
        def fail_second(blueprint,transform):
            if transform.distance: return None
            actor=NS(destroyed=False,set_autopilot=lambda value:None)
            actor.destroy=lambda:setattr(actor,"destroyed",True)
            failures.append(actor)
            return actor
        world.try_spawn_actor=fail_second
        with self.assertRaisesRegex(ValueError,"target"):
            with construction.stage_native_lane_case(
                    world,site,prefix+"left_signal_before_clear_gap",object()):pass
        self.assertTrue(failures[0].destroyed)

    def test_site_camera_poses_rotate_with_selected_native_spawn(self):
        fake_carla=NS(Location=lambda **kwargs:NS(**kwargs),
                      Rotation=lambda **kwargs:NS(**kwargs),
                      Transform=lambda location,rotation:NS(location=location,rotation=rotation))
        site={"spawn":NS(location=NS(x=10,y=20,z=1),rotation=NS(yaw=90))}
        poses=construction.camera_transforms_for_site(fake_carla,site)
        self.assertEqual(set(poses),set(construction.CAMERA_SIZES))
        self.assertAlmostEqual(poses["overview"].location.x,10)
        self.assertAlmostEqual(poses["overview"].location.y,85)
        self.assertEqual(poses["overview"].location.z,49)
        self.assertEqual(poses["approach"].rotation.yaw,75)
        self.assertEqual(poses["driver_reference"].location.x,.8)
        shifted=construction.camera_transforms_for_site(fake_carla,site,75)
        self.assertAlmostEqual(shifted["overview"].location.y,95)
        with self.assertRaisesRegex(ValueError,"Finite selected Native site pose"):
            construction.camera_transforms_for_site(fake_carla,{"spawn":NS(
                location=NS(x=0,y=0,z=0),rotation=NS(yaw=float("nan")))})

    def test_native_camera_sources_join_frames_and_release_sensors(self):
        spawned=[]
        class Blueprint:
            def __init__(self):self.attrs={}
            def set_attribute(self,key,value):self.attrs[key]=value
        def spawn(blueprint,transform,**kwargs):
            sensor=NS(attrs=dict(blueprint.attrs),transform=transform,kwargs=kwargs,
                      stopped=False,destroyed=False,callback=None)
            sensor.listen=lambda callback:setattr(sensor,"callback",callback)
            sensor.stop=lambda:setattr(sensor,"stopped",True)
            sensor.destroy=lambda:setattr(sensor,"destroyed",True)
            spawned.append(sensor)
            return sensor
        world=NS(get_blueprint_library=lambda:NS(find=lambda name:Blueprint()),spawn_actor=spawn)
        ego=object();transforms={name:object() for name in construction.CAMERA_SIZES}
        with construction.source_cameras(world,ego,transforms,timeout_s=.01) as sources:
            self.assertEqual(set(sources),set(construction.CAMERA_SIZES))
            for name,sensor in zip(construction.CAMERA_SIZES,spawned):
                width,height=construction.CAMERA_SIZES[name]
                self.assertEqual(sensor.attrs["image_size_x"],str(width))
                self.assertEqual(sensor.attrs["image_size_y"],str(height))
                self.assertEqual(sensor.attrs["sensor_tick"],"0.05")
                self.assertEqual(sensor.kwargs,({"attach_to":ego} if name=="driver_reference" else {}))
                sensor.callback(NS(frame=9))
                sensor.callback(NS(frame=10))
                self.assertEqual(sources[name](10).frame,10)
            spawned[0].callback(NS(frame=12))
            with self.assertRaisesRegex(ValueError,"skipped expected frame"):
                sources["overview"](11)
            with self.assertRaisesRegex(ValueError,"Missing original Native camera frame"):
                sources["approach"](11)
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in spawned))

    def test_original_camera_ffv1_encoder_retains_bgr_pixels(self):
        repo=ROOT.parents[1]
        scratch=repo/".runtime-work"/"c144550-camera-writer-test"
        scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            path=Path(tmp)/"overview.mkv"
            writer=construction.FFV1CameraWriter(path,4,2,expected_frames=2)
            first=bytes(channel for blue in range(8) for channel in (blue*20,40,90,255))
            second=bytes(channel for blue in range(8) for channel in (200-blue*20,80,30,255))
            try:
                with self.assertRaisesRegex(ValueError,"dimensions"):
                    writer.write(NS(width=2,height=2,raw_data=first))
                writer.write(NS(width=4,height=2,raw_data=first))
                writer.write(NS(width=4,height=2,raw_data=second))
            finally:
                writer.close()
            self.assertEqual(writer.require_complete()["frames"],2)
            decoded=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-i",str(path),
                                    "-f","rawvideo","-pix_fmt","bgr0","pipe:1"],
                                   capture_output=True,check=True).stdout
            self.assertEqual(len(decoded),64)
            for source,returned in zip((first,second),(decoded[:32],decoded[32:])):
                for offset in range(0,32,4):
                    self.assertEqual(returned[offset:offset+3],source[offset:offset+3])
            with self.assertRaisesRegex(ValueError,"Fresh camera source path"):
                construction.FFV1CameraWriter(path,4,2,expected_frames=2)

    def fixture(self,root,indicator=("left","left","left")):
        ctx={"native_map_id":"TownX","road_id":7,"source_lane_id":-1,
             "target_lane_id":-2,"marked_lane_source":"native-marking-and-camera",
             "same_direction_lane_count_source":"native-lane-links",
             "lane_boundary_source":"native-map-polygon",
             "target_traffic_source":"native-actor-bodies",
             "signal_display_source":"original-detail-camera",
             "same_direction_marked_lane_count":2,"change_direction":"left",
             "same_direction_lanes":[
                 {"road_id":7,"lane_id":-1,"forward_xy":[1,0],"marking_source":"native-marking-and-camera"},
                 {"road_id":7,"lane_id":-2,"forward_xy":[1,0],"marking_source":"native-marking-and-camera"}],
             "source_lane_polygon_xy_m":[[0,-3],[100,-3],[100,0],[0,0]],
             "lane_forward_xy":[1,0]}
        (root/"lane_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(x,y) in enumerate(((10,-1),(11,0),(12,1))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"road_id":7,
                         "indicator":indicator[i],"ego_body_vertices_xy_m":body(x,y),
                         "target_lane_bodies":[{"road_id":7,"lane_id":-2,
                                                "body_vertices_xy_m":body(20,1.5)}]})
        frames=[{"video_frame":i,"carla_frame":row["frame"],"time_s":row["time_s"]}
                for i,row in enumerate(rows)]
        (root/"lane_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_appropriate_signal_precedes_first_body_departure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["appropriate_signal_observed_before_movement"])
            self.assertEqual(result["same_direction_lane_ids"],[-2,-1])
            self.assertEqual(result["first_body_leaves_lane"]["frame"],101)
            self.assertIsNotNone(result["samples"][1]["nearest_target_body_longitudinal_gap_m"])
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,("off","off","left"))
            self.assertFalse(measure.analyze(root)["appropriate_signal_observed_before_movement"])

    def test_stale_frame_and_missing_target_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)
            self.fixture(root)
            rows=[json.loads(r) for r in (root/"lane_history.jsonl").read_text().splitlines()]
            del rows[1]["target_lane_bodies"]
            (root/"lane_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"participant inventory"):measure.analyze(root)

    def test_forward_polygon_exit_does_not_count_as_lateral_lane_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(line) for line in (root/"lane_history.jsonl").read_text().splitlines()]
            for row,x in zip(rows,(98,99,101)):
                row["ego_body_vertices_xy_m"]=body(x,-1)
            (root/"lane_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"longitudinal extent exhausted"):
                measure.analyze(root)

    def test_claimed_same_direction_lane_inventory_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/"lane_context.json").read_text())
            ctx["same_direction_lanes"][1]["forward_xy"]=[-1,0]
            (root/"lane_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"Opposing lane"):
                measure.analyze(root)
            ctx["same_direction_lanes"][1]["forward_xy"]=[1,0]
            ctx["same_direction_lanes"][1]["lane_id"]=1
            (root/"lane_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"missing from same-direction inventory"):
                measure.analyze(root)
            ctx["same_direction_lanes"][1]["lane_id"]=-2
            ctx["same_direction_marked_lane_count"]=3
            (root/"lane_context.json").write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,"inventory/count mismatch"):
                measure.analyze(root)

    def test_saved_exact_measurement_preserves_sources_and_unresolved_judgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            case=construction.CASE_PREFIX+"left_signal_before_clear_gap"
            output=root/"saved"/"measurement.json"
            report=measure.write_saved_measurements(root,case,output,expected_frames=3)
            self.assertEqual(json.loads(output.read_text()),report)
            self.assertTrue(report["observed_signal_pattern_matches_plan"])
            self.assertEqual(report["legal_conclusion"],"unresolved")
            self.assertEqual(report["driver_ascertained_safety_judgment"],"unresolved")
            self.assertEqual(report["observed"]["nearest_target_body_longitudinal_gap_at_movement_m"],8.0)
            for name,digest in report["sources"].items():
                self.assertEqual(digest,hashlib.sha256((root/name).read_bytes()).hexdigest())

    def test_saved_exact_measurement_records_realized_signal_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,("off","off","left"))
            before=construction.CASE_PREFIX+"left_signal_before_clear_gap"
            late=construction.CASE_PREFIX+"left_signal_late_clear_gap"
            self.assertFalse(measure.measure_exact_case(root,before,3)["observed_signal_pattern_matches_plan"])
            self.assertFalse(measure.measure_exact_case(root,late,3)["observed_signal_pattern_matches_plan"])
            self.fixture(root,("right","right","right"))
            wrong=construction.CASE_PREFIX+"left_wrong_signal_clear_gap"
            report=measure.measure_exact_case(root,wrong,3)
            self.assertTrue(report["observed_signal_pattern_matches_plan"])
            self.assertFalse(report["observed"]["appropriate_signal_before_movement"])
            self.assertEqual(report["observed"]["indicator_at_movement"],"right")

    def test_saved_exact_measurement_rejects_wrong_case_direction_and_short_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            prefix=construction.CASE_PREFIX
            with self.assertRaisesRegex(ValueError,"Unknown exact"):
                measure.measure_exact_case(root,prefix+"unplanned",3)
            with self.assertRaisesRegex(ValueError,"frame count"):
                measure.measure_exact_case(root,prefix+"left_signal_before_clear_gap")
            with self.assertRaisesRegex(ValueError,"direction differ"):
                measure.measure_exact_case(root,prefix+"right_signal_before_clear_gap",3)
            ctx=json.loads((root/"lane_context.json").read_text())
            ctx["change_direction"]="right"
            (root/"lane_context.json").write_text(json.dumps(ctx))
            report=measure.measure_exact_case(root,prefix+"right_signal_before_clear_gap",3)
            self.assertFalse(report["observed_signal_pattern_matches_plan"])

    def test_capture_rows_persist_as_original_saved_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            context=json.loads((root/"lane_context.json").read_text())
            rows=[json.loads(line) for line in (root/"lane_history.jsonl").read_text().splitlines()]
            retained=root/"retained"
            observed=measure.persist_original_sources(retained,context,rows,3)
            self.assertEqual(observed["first_body_leaves_lane"]["frame"],101)
            case=construction.CASE_PREFIX+"left_signal_before_clear_gap"
            report=measure.write_saved_measurements(retained,case,root/"report.json",3)
            self.assertEqual(report["sources"],observed["sources"])
            with self.assertRaisesRegex(ValueError,"already exist"):
                measure.persist_original_sources(retained,context,rows,3)
            broken=[dict(row) for row in rows]
            del broken[1]["indicator"]
            rejected=root/"rejected"
            with self.assertRaisesRegex(ValueError,"indicator state"):
                measure.persist_original_sources(rejected,context,broken,3)
            self.assertFalse(any((rejected/name).exists() for name in measure.REQUIRED))

    def test_full_900_frame_saved_measurement_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            context=json.loads((root/"lane_context.json").read_text())
            seed=[json.loads(line) for line in (root/"lane_history.jsonl").read_text().splitlines()]
            rows=[]
            for index in range(900):
                row=dict(seed[min(index,2)])
                row["frame"]=100+index
                row["time_s"]=1+index/20
                row["ego_lane_id"]=-1 if index<2 else -2
                rows.append(row)
            retained=root/"full"
            measure.persist_original_sources(retained,context,rows)
            report=measure.write_saved_measurements(
                retained,construction.CASE_PREFIX+"left_signal_before_clear_gap",
                root/"full-report.json")
            self.assertEqual(report["source_frame_count"],900)
            self.assertTrue(report["observed_signal_pattern_matches_plan"])
            self.assertEqual(report["first_body_leaves_lane"]["frame"],101)
            self.assertEqual(report["legal_conclusion"],"unresolved")
            config={"selected_case_id":construction.CASE_PREFIX+"left_signal_before_clear_gap",
                    "law_id":"NRS-484B-223-1b","cell_id":"C144550","duration_s":45,
                    "rate_hz":20,"recording_description":{"channels":["indicator_state"]},
                    "physical_completion":{"body_key":"ego_body_vertices_xy_m",
                                           "lane_key":"ego_lane_id",
                                           "destination_lane":-2,
                                           "context_sources":["lane_context.json"]}}
            (retained/"config.json").write_text(json.dumps(config))
            (retained/"trace.jsonl").write_text("".join(json.dumps({"frame":r["frame"],
                "time_s":r["time_s"],"position_m":[12,1,0]})+"\n" for r in rows))
            for camera in ("overview.mkv","approach.mkv","reference_corner.mkv","driver_reference.mkv"):
                (retained/camera).write_bytes(b"unit-test-placeholder; no pixel claim")
            repo=ROOT.parents[1]
            env=dict(os.environ,PYTHONPATH=str(repo/"runtime"/"scenario_pipeline"),
                     SCENARIO_PIPELINE_OUTPUT_ROOT=str(repo/".runtime-work"/"c144550-finalizer-test"),
                     PYTHONDONTWRITEBYTECODE="1")
            output=retained/"analysis-report.json"
            completed=subprocess.run([sys.executable,str(ROOT/"lane_change_measurements.py"),
                                      "--attempt",str(retained),"--output",str(output)],
                                     env=env,text=True,capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            result=json.loads((retained/"result.json").read_text())
            analysis=json.loads(output.read_text())
            self.assertEqual(result["physical_checks"]["setup"]["status"],"met")
            self.assertEqual(result["physical_checks"]["maneuver"]["status"],"met")
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertFalse(analysis["legal_verdict_asserted"])
            self.assertEqual(len((retained/"channels"/"indicator_state.jsonl").read_text().splitlines()),900)

    def test_physical_lane_binding_rejects_wrong_destination_and_missing_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(line) for line in (root/"lane_history.jsonl").read_text().splitlines()]
            for row in rows:row["ego_lane_id"]=-1
            (root/"lane_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            cfg={"physical_completion":{"body_key":"ego_body_vertices_xy_m",
                                        "lane_key":"ego_lane_id","destination_lane":-1,
                                        "context_sources":["lane_context.json"]}}
            with self.assertRaisesRegex(ValueError,"target lane"):
                measure.validate_physical_binding(root,cfg)
            cfg["physical_completion"]["destination_lane"]=-2
            measure.validate_physical_binding(root,cfg)
            del rows[1]["ego_lane_id"]
            (root/"lane_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"readback missing"):
                measure.validate_physical_binding(root,cfg)

    def test_native_adjacent_marking_both_directions(self):
        mark=NS(type="Solid")
        left=NS(road_id=7,lane_id=-2,lane_type="Driving")
        right=NS(road_id=7,lane_id=-3,lane_type="Driving")
        wp=NS(road_id=7,lane_id=-1,get_left_lane=lambda:left,get_right_lane=lambda:right,
              left_lane_marking=mark,right_lane_marking=mark)
        self.assertIs(construction.select_adjacent_marked_lane(wp,"left","Driving")["target"],left)
        self.assertIs(construction.select_adjacent_marked_lane(wp,"right","Driving")["target"],right)
        right.lane_id=1
        with self.assertRaisesRegex(ValueError,"opposite direction"):
            construction.select_adjacent_marked_lane(wp,"right","Driving")
        right.lane_id=-3
        wp.right_lane_marking=NS(type="None")
        with self.assertRaisesRegex(ValueError,"marking"):
            construction.select_adjacent_marked_lane(wp,"right","Driving")

    def test_native_map_polygon_and_original_actor_observer(self):
        class Waypoint:
            road_id=7
            lane_id=-1
            lane_width=3.5
            def __init__(self,index,y=0,lane_id=-1):
                self.index=index;self.lane_id=lane_id
                self.transform=NS(location=NS(x=2.0*index,y=y),rotation=NS(yaw=0.0))
            def next(self,step):return [Waypoint(self.index+1)]
            def previous(self,step):return [Waypoint(self.index-1)]
        source=Waypoint(0)
        target=Waypoint(0,3.5,-2)
        selected={"source":source,"target":target,"target_lane_id":-2,
                  "marking":NS(type="Broken"),"direction":"left"}
        polygon=construction.sample_source_lane_polygon(source)
        self.assertEqual(len(polygon),272)
        ego_location=NS(x=0.0,y=0.0)
        other_location=NS(x=20.0,y=3.5)
        bounds=NS(get_world_vertices=lambda transform:[NS(x=x,y=y) for x,y in body(
            transform.location.x,transform.location.y)])
        ego=NS(id=1,bounding_box=bounds,get_transform=lambda:NS(location=ego_location),
               get_light_state=lambda:1)
        other=NS(id=2,bounding_box=bounds,get_transform=lambda:NS(location=other_location))
        mapping=NS(name="TownX",get_waypoint=lambda location,project_to_road=False:
                   Waypoint(0,location.y,-2 if location.y>1.75 else -1))
        actors=NS(filter=lambda pattern:[ego,other])
        world=NS(get_map=lambda:mapping,get_actors=lambda:actors)
        context=construction.make_native_lane_context(world,selected,polygon)
        self.assertEqual(context["same_direction_marked_lane_count"],2)
        self.assertEqual(context["target_lane_id"],-2)
        lights=NS(LeftBlinker=1,RightBlinker=2)
        observe=construction.make_original_observer(world,ego,selected,lights,polygon)
        first=observe(100,1.0)
        self.assertEqual(first["indicator"],"left")
        self.assertEqual(first["ego_lane_id"],-1)
        self.assertEqual(first["target_lane_bodies"][0]["actor_id"],2)
        self.assertFalse(first["body_left_source_lane"])
        ego_location.y=2.0
        second=observe(101,1.05)
        self.assertEqual(second["ego_lane_id"],-2)
        self.assertTrue(second["body_left_source_lane"])

    def test_native_site_selector_requires_full_marked_corridor(self):
        class Waypoint:
            road_id=7
            lane_id=-1
            lane_type="Driving"
            lane_width=3.5
            def __init__(self,index,mark="Broken"):
                self.index=index
                self.left_lane_marking=NS(type=mark)
                self.transform=NS(location=NS(x=2.0*index,y=0.0),rotation=NS(yaw=0.0))
            def get_left_lane(self):return NS(road_id=7,lane_id=-2,lane_type="Driving")
            def next(self,step):return [Waypoint(self.index+1)]
            def previous(self,step):return [Waypoint(self.index-1)]
        spawns=[NS(location=NS(x=x,y=0.0,z=0.0)) for x in (40.0,20.0)]
        mapping=NS(get_spawn_points=lambda:spawns,
                   get_waypoint=lambda location,project_to_road=False:
                   Waypoint(round(location.x/2)))
        world=NS(get_map=lambda:mapping)
        site=construction.find_native_lane_site(world,"left","Driving")
        self.assertIs(site["spawn"],spawns[1])
        self.assertEqual(site["candidate_count"],2)
        mapping.get_waypoint=lambda location,project_to_road=False:Waypoint(
            round(location.x/2),"None" if location.x==20 else "Broken")
        self.assertIs(construction.find_native_lane_site(world,"left","Driving")["spawn"],spawns[0])
        mapping.get_waypoint=lambda location,project_to_road=False:Waypoint(round(location.x/2),"None")
        with self.assertRaisesRegex(ValueError,"No uninterrupted marked"):
            construction.find_native_lane_site(world,"left","Driving")

    def test_exact_case_signal_policy_and_native_readback(self):
        prefix=construction.CASE_PREFIX
        before=prefix+"left_signal_before_clear_gap"
        late=prefix+"left_signal_late_clear_gap"
        wrong=prefix+"left_wrong_signal_clear_gap"
        right=prefix+"right_signal_before_clear_gap"
        self.assertEqual(construction.indicator_command(before,False),"left")
        self.assertEqual(construction.indicator_command(late,False),"off")
        self.assertEqual(construction.indicator_command(late,True),"left")
        self.assertEqual(construction.indicator_command(wrong,False),"right")
        self.assertEqual(construction.indicator_command(right,False),"right")
        with self.assertRaisesRegex(ValueError,"Unknown exact"):
            construction.indicator_command(prefix+"unplanned",False)
        class Lights(IntFlag):
            LeftBlinker=1
            RightBlinker=2
            LowBeam=4
        vehicle=NS(state=Lights.LowBeam,get_light_state=lambda:vehicle.state,
                   set_light_state=lambda state:setattr(vehicle,"state",state))
        self.assertEqual(construction.apply_indicator(vehicle,Lights,"left")["readback_state"],5)
        self.assertEqual(construction.apply_indicator(vehicle,Lights,"right")["readback_state"],6)
        self.assertEqual(construction.apply_indicator(vehicle,Lights,"off")["readback_state"],4)

    def test_native_control_uses_selected_lane_and_exact_indicator(self):
        class Lights(IntFlag):
            LeftBlinker=1
            RightBlinker=2
            LowBeam=4
        ego=NS(state=Lights.LowBeam,control=None,
               get_light_state=lambda:ego.state,
               set_light_state=lambda state:setattr(ego,"state",state),
               get_transform=lambda:NS(location=NS(x=0.0,y=0.0),rotation=NS(yaw=0.0)),
               get_velocity=lambda:NS(x=2.0,y=0.0,z=0.0),
               apply_control=lambda control:setattr(ego,"control",control))
        left=NS(transform=NS(location=NS(x=8.0,y=3.5)))
        selected={"direction":"left","target":left,"target_lane_id":-2}
        make_control=lambda **kwargs:NS(**kwargs)
        before=construction.CASE_PREFIX+"left_signal_before_clear_gap"
        result=construction.step_toward_marked_lane(
            ego,selected,before,False,Lights,make_control)
        self.assertGreater(result["control"].steer,0)
        self.assertEqual(result["signal"]["readback_state"],5)
        self.assertEqual(result["target_lane_id"],-2)
        self.assertFalse(result["control"].reverse)
        self.assertIs(result["control"],ego.control)
        self.assertEqual(result["legal_safety_ascertainment"],"unresolved")
        late=construction.CASE_PREFIX+"left_signal_late_clear_gap"
        result=construction.step_toward_marked_lane(
            ego,selected,late,False,Lights,make_control)
        self.assertEqual(result["signal"]["readback_state"],4)
        with self.assertRaisesRegex(ValueError,"direction differ"):
            construction.step_toward_marked_lane(
                ego,selected,construction.CASE_PREFIX+"right_signal_before_clear_gap",
                False,Lights,make_control)
        right={"direction":"right","target":NS(transform=NS(location=NS(x=8.0,y=-3.5))),
               "target_lane_id":-3}
        result=construction.step_toward_marked_lane(
            ego,right,construction.CASE_PREFIX+"right_signal_before_clear_gap",
            False,Lights,make_control)
        self.assertLess(result["control"].steer,0)
        self.assertEqual(result["signal"]["readback_state"],6)

    def test_route_target_advances_after_initial_target_is_passed(self):
        current_location=NS(x=30.0,y=0.0)
        ego=NS(get_transform=lambda:NS(location=current_location))
        target=NS(road_id=7,lane_id=-2)
        target.next=lambda distance:[NS(road_id=7,lane_id=-2,
                                        transform=NS(location=NS(x=current_location.x+distance,y=3.5)))]
        source=NS(road_id=7,lane_id=-1,get_left_lane=lambda:target)
        mapping=NS(get_waypoint=lambda location,project_to_road=False:source)
        world=NS(get_map=lambda:mapping)
        selected={"source":source,"source_lane_id":-1,"target_lane_id":-2,
                  "direction":"left","target":NS(transform=NS(location=NS(x=0.0,y=3.5)))}
        ahead=construction.route_target_for_tick(world,ego,selected)
        self.assertEqual(ahead.transform.location.x,38)
        mapping.get_waypoint=lambda location,project_to_road=False:target
        current_location.y=3.5
        self.assertEqual(construction.route_target_for_tick(world,ego,selected).transform.location.x,38)
        mapping.get_waypoint=lambda location,project_to_road=False:NS(road_id=7,lane_id=-3)
        with self.assertRaisesRegex(ValueError,"unselected lane"):
            construction.route_target_for_tick(world,ego,selected)

    def test_exact_native_capture_core_joins_four_cameras_and_closes(self):
        repo=ROOT.parents[1]
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]=str(repo/".runtime-work"/"c144550-frame-map-test")
        sys.path.insert(0,str(repo/"runtime"/"scenario_pipeline"))
        from worker_exchange.native_output import FrameMap
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        retained=Path(tmp.name)
        class Lights(IntFlag):
            LeftBlinker=1
            RightBlinker=2
        ego=NS(state=Lights(0),get_light_state=lambda:ego.state,
               set_light_state=lambda state:setattr(ego,"state",state),
               get_transform=lambda:NS(location=NS(x=0.0,y=0.0),rotation=NS(yaw=0.0)),
               get_velocity=lambda:NS(x=2.0,y=0.0,z=0.0),apply_control=lambda control:None)
        target_lane=NS(road_id=7,lane_id=-2,
                       next=lambda distance:[NS(road_id=7,lane_id=-2,
                                                transform=NS(location=NS(x=8.0,y=3.5)))])
        source_lane=NS(road_id=7,lane_id=-1,get_left_lane=lambda:target_lane)
        mapping=NS(get_waypoint=lambda location,project_to_road=False:source_lane)
        world=NS(frame=0,tick=lambda:None,get_snapshot=lambda:None,get_map=lambda:mapping)
        def tick():
            world.frame+=1
            return world.frame
        world.tick=tick
        world.get_snapshot=lambda:NS(timestamp=NS(elapsed_seconds=world.frame/20))
        names=("overview","approach","reference_corner","driver_reference")
        writers={name:NS(frames=[],closed=False) for name in names}
        for writer in writers.values():
            writer.write=lambda image,w=writer:w.frames.append(image.frame)
            writer.close=lambda w=writer:setattr(w,"closed",True)
            writer.require_complete=lambda w=writer:self.assertEqual(len(w.frames),900)
        cameras={name:(lambda frame:NS(frame=frame)) for name in names}
        selected={"direction":"left","source":source_lane,"source_lane_id":-1,
                  "target":NS(transform=NS(location=NS(x=8.0,y=3.5))),"target_lane_id":-2}
        observe=lambda frame,time:{"frame":frame,"time_s":time,
                                   "body_left_source_lane":frame>100}
        frame_map=FrameMap(retained/"video_frames.jsonl")
        history=(retained/"lane_history.jsonl").open("x")
        pipeline_frames=[]
        capture_pipeline=lambda frame,time:pipeline_frames.append((frame,time))
        rows=construction.capture_native_case(
            world,ego,selected,construction.CASE_PREFIX+"left_signal_late_clear_gap",
            Lights,lambda **kwargs:NS(**kwargs),observe,cameras,writers,
            frame_map,history,capture_pipeline)
        self.assertEqual(len(rows),900)
        self.assertEqual(rows[0]["requested_indicator"],"off")
        self.assertEqual(rows[101]["requested_indicator"],"left")
        self.assertTrue(all(len(w.frames)==900 and w.closed for w in writers.values()))
        mapped=[json.loads(line) for line in (retained/"video_frames.jsonl").read_text().splitlines()]
        saved=[json.loads(line) for line in (retained/"lane_history.jsonl").read_text().splitlines()]
        self.assertEqual(mapped[0]["carla_frame"],1)
        self.assertEqual(mapped[-1]["time_s"],45.0)
        self.assertEqual(len(mapped),len(saved))
        self.assertEqual(pipeline_frames,[(row["carla_frame"],row["time_s"]) for row in mapped])
        self.assertEqual(saved[101]["frame"],mapped[101]["carla_frame"])
        self.assertTrue(frame_map.stream.closed and history.closed)
        world.frame=0
        for writer in writers.values():
            writer.frames=[];writer.closed=False
        frame_map=FrameMap(retained/"failed_video_frames.jsonl")
        history=(retained/"failed_lane_history.jsonl").open("x")
        cameras["overview"]=lambda frame:NS(frame=frame+1)
        with self.assertRaisesRegex(ValueError,"Camera skipped"):
            construction.capture_native_case(
                world,ego,selected,construction.CASE_PREFIX+"left_signal_before_clear_gap",
                Lights,lambda **kwargs:NS(**kwargs),observe,cameras,writers,
                frame_map,history,capture_pipeline)
        self.assertTrue(all(w.closed for w in writers.values()))
        self.assertTrue(frame_map.stream.closed and history.closed)
        self.assertEqual((retained/"failed_video_frames.jsonl").read_text(),"")
        self.assertEqual((retained/"failed_lane_history.jsonl").read_text(),"")
        self.assertEqual(len(pipeline_frames),900)
        world.frame=0
        cameras["overview"]=lambda frame:NS(frame=frame)
        for writer in writers.values():writer.frames=[];writer.closed=False
        writers["overview"].close=lambda:(_ for _ in ()).throw(ValueError("encoder close failed"))
        frame_map=FrameMap(retained/"closure_video_frames.jsonl")
        history=(retained/"closure_lane_history.jsonl").open("x")
        with self.assertRaisesRegex(ValueError,"encoder close failed"):
            construction.capture_native_case(
                world,ego,selected,construction.CASE_PREFIX+"left_signal_before_clear_gap",
                Lights,lambda **kwargs:NS(**kwargs),observe,cameras,writers,
                frame_map,history,capture_pipeline)
        self.assertTrue(frame_map.stream.closed and history.closed)
        self.assertTrue(all(w.closed for name,w in writers.items() if name!="overview"))


if __name__=="__main__":unittest.main()
