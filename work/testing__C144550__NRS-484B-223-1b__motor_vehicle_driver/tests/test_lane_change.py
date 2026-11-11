import importlib.util
import json
import tempfile
import unittest
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
    def fixture(self,root,indicator=("left","left","left")):
        ctx={"native_map_id":"TownX","road_id":7,"source_lane_id":-1,
             "target_lane_id":-2,"marked_lane_source":"native-marking-and-camera",
             "same_direction_lane_count_source":"native-lane-links",
             "lane_boundary_source":"native-map-polygon",
             "target_traffic_source":"native-actor-bodies",
             "signal_display_source":"original-detail-camera",
             "same_direction_marked_lane_count":2,"change_direction":"left",
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

    def test_native_adjacent_marking_both_directions(self):
        mark=NS(type="Solid")
        left=NS(road_id=7,lane_id=-2,lane_type="Driving")
        right=NS(road_id=7,lane_id=1,lane_type="Driving")
        wp=NS(road_id=7,lane_id=-1,get_left_lane=lambda:left,get_right_lane=lambda:right,
              left_lane_marking=mark,right_lane_marking=mark)
        self.assertIs(construction.select_adjacent_marked_lane(wp,"left","Driving")["target"],left)
        self.assertIs(construction.select_adjacent_marked_lane(wp,"right","Driving")["target"],right)
        wp.right_lane_marking=NS(type="None")
        with self.assertRaisesRegex(ValueError,"marking"):
            construction.select_adjacent_marked_lane(wp,"right","Driving")


if __name__=="__main__":unittest.main()
