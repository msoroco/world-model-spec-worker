import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

measure = load("departure_measurements")
selection = load("native_road_selection")
site = load("site_review")
departure_route = load("departure_route")
turn_control = load("turn_control")


def body(x, y):
    return [[x, y-.4], [x, y+.4], [x+2, y+.4], [x+2, y-.4]]

class DepartureTests(unittest.TestCase):
    def test_paired_left_turn_departure_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ('approach_road_source', 'outgoing_road_source',
                     'destination_centerline_source', 'destination_right_half_source',
                     'junction_source')
            refs = {}
            for name in names:
                path = root / (name+'.txt')
                path.write_text('Synthetic '+name)
                refs[name] = {'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            points = [NS(road_id=road,lane_id=lane,lane_type='Driving')
                      for road in (1,2) for lane in (-1,1)]
            world = NS(get_map=lambda:NS(name='TownX',generate_waypoints=lambda spacing:points))
            packet = {'native_map_id':'TownX','intersection_id':44,
                      'approach_road_id':1,'outgoing_road_id':2,
                      'approach_lane_id':-1,'outgoing_lane_id':-1,
                      'centerline_kind':'marked','destination_centerline_xy_m':[[0,0],[0,25]],
                      'destination_right_half_polygon_xy_m':[[0,0],[6,0],[6,25],[0,25]],
                      'junction_polygon_xy_m':[[-5,-5],[5,-5],[5,5],[-5,5]],
                      'route_near_xy_m':[[-15,-2],[-6,-2],[-2,-2],[2.5,1],[2.5,8],[2.5,18]],
                      'route_far_xy_m':[[-15,-2],[-6,-2],[-2,-2],[3.5,1],[3.5,8],[3.5,18]],
                      'exit_body_clearance_radius_m':.8,
                      'reviewer':'CPU fixture','review_basis':'synthetic route proof only',**refs}
            near = departure_route.plan(world,packet,root,farther=False)
            far = departure_route.plan(world,packet,root,farther=True)
            self.assertGreater(far['destination_exit_clearance_m'],near['destination_exit_clearance_m'])
            self.assertFalse(far['physical_completion_claimed'])
            for planned in (near, far):
                route = planned['route_xy_m']
                follower = turn_control.RouteFollower(route, target_speed_mps=3)
                self.assertGreater(follower.step(route[0],[1,0],0)['throttle'],0)
                follower.step(route[1],[1,0],2)
                self.assertGreater(follower.step(route[2],[1,0],2)['steer'],0)
                follower.step(route[3],[0,1],2)
                follower.step(route[4],[0,1],2)
                self.assertTrue(follower.step(route[-1],[0,1],0)['route_complete'])
            packet['route_far_xy_m'][-1] = [2.6,18]
            with self.assertRaisesRegex(ValueError,'not measurably farther'):
                departure_route.plan(world,packet,root,farther=True)
            packet['route_far_xy_m'][-1] = [3.5,18]
            packet['route_near_xy_m'][-1] = [-1,18]
            with self.assertRaisesRegex(ValueError,'Complete exit body crosses'):
                departure_route.plan(world,packet,root,farther=False)
    def test_destination_site_source_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ('approach_road_source', 'outgoing_road_source',
                     'destination_centerline_source', 'destination_right_half_source',
                     'junction_source')
            refs = {}
            for name in names:
                path = root / (name + '.txt')
                path.write_text('Synthetic CPU geometry source for ' + name)
                refs[name] = {'path': path.name,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            points = [NS(road_id=road, lane_id=lane, lane_type='Driving')
                      for road in (1, 2) for lane in (-1, 1)]
            world = NS(get_map=lambda: NS(name='TownX',
                       generate_waypoints=lambda spacing: points))
            packet = {'native_map_id':'TownX', 'intersection_id':44,
                      'approach_road_id':1, 'outgoing_road_id':2,
                      'centerline_kind':'marked',
                      'destination_centerline_xy_m':[[0,0],[30,0]],
                      'destination_right_half_polygon_xy_m':[[0,0],[30,0],[30,-5],[0,-5]],
                      'junction_polygon_xy_m':[[0,-6],[10,-6],[10,6],[0,6]],
                      'reviewer':'CPU fixture', 'review_basis':'synthetic source checks only',
                      **refs}
            review = site.validate(packet, root, world)
            self.assertEqual(review['centerline_kind'], 'marked')
            self.assertEqual(review['physical_exit_position'], 'unverified')
            packet['centerline_kind'] = 'imaginary'
            self.assertEqual(site.validate(packet, root, world)['centerline_kind'], 'imaginary')
            (root/'destination_centerline_source.txt').write_text('Changed source')
            with self.assertRaisesRegex(ValueError, 'Stale or missing destination_centerline_source'):
                site.validate(packet, root, world)
            packet['destination_centerline_source']['sha256'] = hashlib.sha256(
                (root/'destination_centerline_source.txt').read_bytes()).hexdigest()
            packet['outgoing_road_id'] = 3
            with self.assertRaisesRegex(ValueError, 'Opposite-direction Native driving lanes missing'):
                site.validate(packet, root, world)
    def fixture(self, root, exit_y=-1, exit_road=2):
        ctx = {"native_map_id":"TownX", "intersection_id":44,
               "approach_road_id":1, "outgoing_road_id":2,
               "opposing_lane_source":"native-waypoint-inventory",
               "destination_centerline_source":"native-map-and-front-video",
               "destination_right_half_source":"native-road-boundary",
               "junction_source":"native-junction", "left_turn_route_source":"native-waypoint-chain",
               "both_highways_two_directional":True, "intended_turn":"left",
               "destination_centerline_xy_m":[[0,0],[100,0]],
               "destination_right_half_polygon_xy_m":[[0,0],[100,0],[100,-5],[0,-5]],
               "junction_polygon_xy_m":[[0,-6],[10,-6],[10,6],[0,6]]}
        (root/"road_context.json").write_text(json.dumps(ctx))
        rows = [{"frame":100+i, "time_s":1+i*.05, "road_id":road,
                 "ego_body_vertices_xy_m":body(x,y)}
                for i,(x,y,road) in enumerate([(-4,-1,1),(5,-1,1),(12,exit_y,exit_road)])]
        frames = [{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]}
                  for i,r in enumerate(rows)]
        (root/"turn_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_exit_right_near_far_and_wrong_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root,-1)
            near = measure.analyze(root)
            self.assertTrue(near["exit_sample"]["complete_body_right_of_destination_centerline"])
            self.fixture(root,-3)
            far = measure.analyze(root)
            self.assertGreater(far["exit_sample"]["body_centroid_distance_to_centerline_m"],near["exit_sample"]["body_centroid_distance_to_centerline_m"])
            self.fixture(root,1)
            self.assertFalse(measure.analyze(root)["exit_sample"]["complete_body_right_of_destination_centerline"])

    def test_wrong_road_stale_frame_and_no_exit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root,exit_road=3)
            with self.assertRaisesRegex(ValueError,"destination road"): measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(s) for s in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[2]["carla_frame"]=888
            (root/"video_frames.jsonl").write_text("".join(json.dumps(s)+"\n" for s in frames))
            with self.assertRaisesRegex(ValueError,"frame join"): measure.analyze(root)
            self.fixture(root)
            rows=[json.loads(s) for s in (root/"turn_history.jsonl").read_text().splitlines()]
            rows[2]["ego_body_vertices_xy_m"]=body(6,-1)
            (root/"turn_history.jsonl").write_text("".join(json.dumps(s)+"\n" for s in rows))
            with self.assertRaisesRegex(ValueError,"complete-body exit"): measure.analyze(root)

    def test_both_roads_require_opposing_native_lanes(self):
        def wp(r,l): return NS(road_id=r,lane_id=l,lane_type="Driving")
        waypoints=[wp(1,-1),wp(1,1),wp(2,-1),wp(2,1)]
        world=NS(get_map=lambda:NS(generate_waypoints=lambda spacing:waypoints))
        self.assertEqual(selection.verify_two_directional_roads(world,1,2)["native_lane_ids"],{"1":[-1,1],"2":[-1,1]})
        waypoints.pop()
        with self.assertRaisesRegex(ValueError,"Opposite-direction"): selection.verify_two_directional_roads(world,1,2)

    def test_saved_destination_finalizer_uses_original_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            context = json.loads((root / "road_context.json").read_text())
            context["site_source_review"] = {"centerline_kind": "marked"}
            (root / "road_context.json").write_text(json.dumps(context))
            case = "testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__source_verified_near_centerline"
            config = {"law_id": "NRS-484B-400-2b", "cell_id": "C109705",
                      "actor": "motor_vehicle_driver", "selected_case_id": case,
                      "supported_case_ids": [case],
                      "recording_description": {"channels": [{"name": "destination_exit"}]}}
            (root / "config.json").write_text(json.dumps(config))
            (root / "site_packet.json").write_text(json.dumps({"centerline_kind": "marked"}))
            rows = [json.loads(s) for s in (root / "turn_history.jsonl").read_text().splitlines()]
            (root / "trace.jsonl").write_text("".join(json.dumps({"frame": r["frame"],
                "time_s": r["time_s"]}) + "\n" for r in rows))
            (root / "capture").mkdir()
            (root / "capture/evidence.jsonl").write_text("{}\n")
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                (root / (name + ".mkv")).write_bytes(b"unit-test-only")
            report = measure.finalize(root, root / "analysis-report.json")
            self.assertFalse(report["physical_acceptance_claimed"])
            self.assertTrue(report["measurements"]["complete_body_right_of_destination_centerline"])
            self.assertTrue((root / "channels/destination_exit.jsonl").is_file())
            self.assertEqual(json.loads((root / "result.json").read_text())["case_id"], case)
            with self.assertRaisesRegex(ValueError, "fresh saved analysis"):
                measure.finalize(root, root / "second-report.json")
            (root / "result.json").unlink()
            for path in (root / "channels").iterdir(): path.unlink()
            (root / "channels").rmdir()
            (root / "analysis-report.json").unlink()
            self.fixture(root, exit_y=1)
            (root / "road_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "Complete exit body crosses"):
                measure.finalize(root, root / "analysis-report.json")

if __name__ == "__main__": unittest.main()
