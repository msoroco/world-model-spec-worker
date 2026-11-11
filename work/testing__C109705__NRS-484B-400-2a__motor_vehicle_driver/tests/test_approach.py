import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


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
    def fixture(self,root,lateral):
        ctx={"native_map_id":"TownX","intersection_id":44,"approach_road_id":1,
             "approach_lane_id":-1,"outgoing_road_id":2,
             "opposing_lane_source":"native-lane-links","centerline_source":"native-map-and-front-video",
             "right_half_source":"native-road-boundary","junction_source":"native-junction",
             "left_turn_route_source":"native-waypoint-chain","both_highways_two_directional":True,
             "intended_turn":"left","centerline_xy_m":[[0,0],[100,0]],
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
