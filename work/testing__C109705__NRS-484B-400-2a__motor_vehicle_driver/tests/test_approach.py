import importlib.util
import hashlib
import sys
from queue import Queue
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/"runtime"/"scenario_pipeline"))


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


measure=load("approach_measurements")
selection=load("native_road_selection")


def body(y):
    return [[x,yy] for x,yy in ((10,y-.5),(10,y+.5),(12,y+.5),(12,y-.5))]


class ApproachTests(unittest.TestCase):
    def site_fixture(self, root):
        names=("approach_road_source", "outgoing_road_source", "centerline_source",
               "right_half_source", "junction_source", "route_source")
        packet={"native_map_id":"TownX", "intersection_id":44,
                "approach_road_id":1, "approach_lane_id":-1, "connector_road_id":3,
                "outgoing_road_id":2, "departure_direction_xy":[0,1],
                "vehicle_blueprint_id":"vehicle.tesla.model3",
                "centerline_kind":"marked", "centerline_xy_m":[[0,0],[20,0]],
                "right_half_polygon_xy_m":[[0,0],[20,0],[20,-5],[0,-5]],
                "junction_polygon_xy_m":[[14,-6],[24,-6],[24,4],[14,4]],
                "approach_route_xy_m":[[2,-2],[16,-2]],
                "left_turn_route_xy_m":[[2,-2],[16,-2],[19,0],[19,3],[19,8]],
                "start_z_m":0.8,
                "reviewer":"CPU fixture", "review_basis":"synthetic geometry test"}
        for name in names:
            path=root/(name+".txt")
            path.write_text(name)
            packet[name]={"path":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
        def wp(road,lane):return NS(road_id=road,lane_id=lane,lane_type="Driving")
        waypoints=[wp(1,-1),wp(1,1),wp(2,-1),wp(2,1)]
        world=NS(get_map=lambda:NS(name="TownX",generate_waypoints=lambda spacing:waypoints))
        return packet,world

    def test_reviewed_approach_site_binds_native_lanes_and_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,world=self.site_fixture(root)
            result=selection.validate_approach_site(world,packet,root)
            self.assertEqual(result["physical_approach_position"],"unverified")
            self.assertEqual(len(result["sources"]),6)
            packet["approach_route_xy_m"]=[[2,1],[16,1]]
            with self.assertRaisesRegex(ValueError,"geometry differs"):
                selection.validate_approach_site(world,packet,root)

    def test_reviewed_approach_site_rejects_stale_source_or_wrong_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,world=self.site_fixture(root)
            (root/"route_source.txt").write_text("altered")
            with self.assertRaisesRegex(ValueError,"Stale or missing route_source"):
                selection.validate_approach_site(world,packet,root)
            packet,world=self.site_fixture(root)
            packet["native_map_id"]="OtherTown"
            with self.assertRaisesRegex(ValueError,"Native map"):
                selection.validate_approach_site(world,packet,root)

    def test_reviewed_approach_site_rejects_absent_selected_lane(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,world=self.site_fixture(root)
            packet["approach_lane_id"]=-2
            with self.assertRaisesRegex(ValueError,"Selected approach lane"):
                selection.validate_approach_site(world,packet,root)

    def test_left_turn_route_controller_and_four_original_camera_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet,world=self.site_fixture(root)
            construction=selection.plan_left_turn(world,packet,root)
            route=construction["route_xy_m"]
            self.assertFalse(construction["physical_completion_claimed"])
            cameras=selection.four_camera_plan(packet,route)
            self.assertEqual([item["name"] for item in cameras],
                             ["overview","approach","reference_corner","driver_reference"])
            self.assertEqual(cameras[3]["mount"],"ego_vehicle")
            self.assertTrue(all(not item["visibility_verified"] for item in cameras))
            follower=selection.RouteFollower(route,target_speed_mps=3)
            self.assertGreater(follower.step(route[0],[1,0],0)["throttle"],0)
            for point in route[1:-1]:
                follower.step(point,[1,0],3)
            self.assertEqual(follower.step(route[-1],[0,1],3)["brake"],1)
            packet["left_turn_route_xy_m"]=[[2,-2],[16,-2],[19,-3],[19,-8]]
            with self.assertRaisesRegex(ValueError,"left turn"):
                selection.plan_left_turn(world,packet,root)
            packet["left_turn_route_xy_m"]=[[2,-3],[16,-2],[19,0],[19,3],[19,8]]
            with self.assertRaisesRegex(ValueError,"preserve reviewed approach"):
                selection.plan_left_turn(world,packet,root)

    def test_four_cameras_spawn_join_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet,_=self.site_fixture(Path(tmp))
            plan=selection.four_camera_plan(packet,packet["left_turn_route_xy_m"])
            spawned=[]
            class Sensor:
                def __init__(self):self.stopped=self.destroyed=False
                def stop(self):self.stopped=True
                def destroy(self):self.destroyed=True
            class Blueprint:
                def __init__(self):self.attributes={}
                def set_attribute(self,k,v):self.attributes[k]=v
            world=NS(get_blueprint_library=lambda:NS(find=lambda name:Blueprint()),
                     spawn_actor=lambda bp,pose,**kwargs:spawned.append((Sensor(),bp,kwargs)) or spawned[-1][0])
            carla=NS(Location=lambda **kw:kw,Rotation=lambda **kw:kw,
                     Transform=lambda location,rotation:(location,rotation))
            with selection.source_cameras(world,object(),carla,plan) as cameras:
                self.assertEqual(set(cameras),set(selection.CAMERA_PROFILE))
                self.assertEqual(len(spawned),4)
                self.assertEqual(spawned[-1][2].keys(),{"attach_to"})
                self.assertEqual(spawned[0][1].attributes["sensor_tick"],"0.05")
            self.assertTrue(all(row[0].stopped and row[0].destroyed for row in spawned))
            queue=Queue();queue.put(NS(frame=7));queue.put(NS(frame=8))
            self.assertEqual(selection._camera_frame(queue,8).frame,8)
            queue=Queue();queue.put(NS(frame=9))
            with self.assertRaisesRegex(ValueError,"skipped"):
                selection._camera_frame(queue,8)

    def fixture(self,root,lateral):
        ctx={"native_map_id":"TownX","intersection_id":44,"approach_road_id":1,
             "approach_lane_id":-1,"outgoing_road_id":2,
             "opposing_lane_source":"native-lane-links","centerline_source":"native-map-and-front-video",
             "right_half_source":"native-road-boundary","junction_source":"native-junction",
             "left_turn_route_source":"native-waypoint-chain","both_highways_two_directional":True,
             "intended_turn":"left","centerline_kind":"marked","centerline_xy_m":[[0,0],[100,0]],
             "right_half_polygon_xy_m":[[0,0],[100,0],[100,-5],[0,-5]]}
        (root/"road_context.json").write_text(json.dumps(ctx))
        rows=[{"frame":100+i,"time_s":1+i*.05,"road_id":1,"lane_id":-1,
               "body_in_intersection":False,"ego_body_vertices_xy_m":body(lateral)}
              for i in range(2)]
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"approach_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_near_far_and_right_half_body_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,-1)
            near=measure.analyze(root)
            self.fixture(root,-3)
            far=measure.analyze(root)
            self.assertTrue(near["all_sampled_bodies_in_right_half"])
            self.assertLess(near["approach_samples"][0]["body_centroid_distance_to_centerline_m"],
                            far["approach_samples"][0]["body_centroid_distance_to_centerline_m"])
            self.assertEqual(near["legal_conclusion"],"unresolved")
            self.fixture(root,1)
            self.assertFalse(measure.analyze(root)["all_sampled_bodies_in_right_half"])

    def test_saved_near_far_comparison_checks_fixed_road_and_measured_order(self):
        with tempfile.TemporaryDirectory() as near_tmp, tempfile.TemporaryDirectory() as far_tmp:
            near,far=Path(near_tmp),Path(far_tmp)
            self.fixture(near,-1);self.fixture(far,-3)
            report=measure.compare_near_far(near,far)
            self.assertLess(report["near_mean_body_centroid_distance_m"],
                            report["far_mean_body_centroid_distance_m"])
            self.assertEqual(report["legal_nearest_judgment"],"unresolved")
            context=json.loads((far/"road_context.json").read_text())
            context["outgoing_road_id"]=7
            (far/"road_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,"Fixed approach road"):
                measure.compare_near_far(near,far)
            self.fixture(far,-.8)
            with self.assertRaisesRegex(ValueError,"measured ordering"):
                measure.compare_near_far(near,far)
            self.fixture(far,1)
            with self.assertRaisesRegex(ValueError,"body leaves"):
                measure.compare_near_far(near,far)

    def test_wrong_road_and_stale_original_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,-1)
            rows=[json.loads(r) for r in (root/"approach_history.jsonl").read_text().splitlines()]
            rows[1]["road_id"]=9
            (root/"approach_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"approach lane"):
                measure.analyze(root)
            self.fixture(root,-1)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                measure.analyze(root)

    def test_approach_prefix_must_end_at_first_sourced_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,-1)
            context=json.loads((root/"road_context.json").read_text())
            context["first_entry_frame"]=102
            (root/"road_context.json").write_text(json.dumps(context))
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames.append({"video_frame":2,"carla_frame":102,"time_s":1.1})
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            self.assertEqual(len(measure.analyze(root)["approach_samples"]),2)
            context["first_entry_frame"]=103
            (root/"road_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,"First intersection entry"):
                measure.analyze(root)

    def test_saved_finalizer_rebuilds_channels_and_rejects_missing_body_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,-1)
            case="testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__source_verified_near_centerline"
            config={"selected_case_id":case,"law_id":"NRS-484B-400-2a",
                    "cell_id":"C109705","actor":"motor_vehicle_driver",
                    "recording_description":{"channels":[]}}
            (root/"config.json").write_text(json.dumps(config))
            rows=[json.loads(r) for r in (root/"approach_history.jsonl").read_text().splitlines()]
            body_rows=[{"frame":r["frame"],"time_s":r["time_s"],
                        "road_id":r["road_id"],"lane_id":r["lane_id"],
                        "body_vertices_m":[v+[0.8] for v in r["ego_body_vertices_xy_m"]]}
                       for r in rows]
            (root/"body_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in body_rows))
            geometry={"intersection_xy_m":[[14,-6],[24,-6],[24,4],[14,4]],
                      "approach_road_id":1,"connector_road_id":3,"departure_road_id":2,
                      "departure_direction_xy":[0,1],"two_way":True}
            (root/"road_geometry.json").write_text(json.dumps(geometry))
            (root/"trace.jsonl").write_text("".join(json.dumps({"frame":r["frame"],
                 "time_s":r["time_s"],"position_m":[11,-1,0.8]})+"\n" for r in rows))
            (root/"capture").mkdir();(root/"capture"/"evidence.jsonl").write_text("{}\n")
            for name in selection.CAMERA_PROFILE:(root/(name+".mkv")).write_bytes(b"fixture-placeholder")
            report=measure.finalize(root,root/"analysis-report.json")
            self.assertEqual(report["case_id"],case)
            self.assertTrue((root/"channels"/"approach_lateral.jsonl").is_file())
            result=json.loads((root/"result.json").read_text())
            self.assertFalse(result["maneuver_completed"])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,-1)
            with self.assertRaisesRegex(ValueError,"Missing required source: config.json"):
                measure.finalize(root,root/"analysis-report.json")

    def test_both_intersecting_native_roads_need_opposing_lanes(self):
        def wp(road,lane):return NS(road_id=road,lane_id=lane,lane_type="Driving")
        waypoints=[wp(1,-1),wp(1,1),wp(2,-1),wp(2,1)]
        world=NS(get_map=lambda:NS(generate_waypoints=lambda spacing:waypoints))
        result=selection.verify_two_directional_roads(world,1,2)
        self.assertEqual(result["native_lane_ids"],{"1":[-1,1],"2":[-1,1]})
        waypoints.pop()
        with self.assertRaisesRegex(ValueError,"Opposite-direction"):
            selection.verify_two_directional_roads(world,1,2)


if __name__=="__main__":
    unittest.main()
