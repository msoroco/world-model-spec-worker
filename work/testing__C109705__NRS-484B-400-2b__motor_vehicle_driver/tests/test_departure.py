import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

measure = load("departure_measurements")
selection = load("native_road_selection")


def body(x, y):
    return [[x, y-.4], [x, y+.4], [x+2, y+.4], [x+2, y-.4]]

class DepartureTests(unittest.TestCase):
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

if __name__ == "__main__": unittest.main()
