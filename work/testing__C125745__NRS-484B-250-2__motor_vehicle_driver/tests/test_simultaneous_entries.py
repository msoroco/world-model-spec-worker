import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("simultaneous_entries",ROOT/"simultaneous_entries.py")
measure=importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)
control_spec=importlib.util.spec_from_file_location("stop_sign_control",ROOT/"stop_sign_control.py")
control=importlib.util.module_from_spec(control_spec)
control_spec.loader.exec_module(control)


def vehicle(x,y,road):
    return {"intersection_id":44,"road_id":road,
            "body_vertices_xy_m":[[x+dx,y+dy] for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1))]}


class EntryTests(unittest.TestCase):
    def test_native_stop_sign_governs_approach(self):
        class Actors(list):
            def filter(self,pattern):return self
        selected=NS(trigger_volume=NS(contains=lambda point,transform:True),get_transform=lambda:"sign")
        wrong=NS(trigger_volume=NS(contains=lambda point,transform:False),get_transform=lambda:"wrong")
        world=NS(get_actors=lambda:Actors([wrong,selected]))
        waypoint=NS(transform=NS(location="approach"))
        self.assertIs(control.find_governing_stop_sign(world,waypoint),selected)
        with self.assertRaisesRegex(ValueError,"found 0"):
            control.find_governing_stop_sign(NS(get_actors=lambda:Actors([wrong])),waypoint)

    def fixture(self,root,other_y=-10):
        ctx={"native_map_id":"TownX","intersection_id":44,
             "ego_highway_id":"east-west","other_highway_id":"north-south",
             "ego_road_id":1,"other_road_id":2,
             "crossing_geometry_source":"native-and-original-camera",
             "all_entrances_source":"native-lane-inventory",
             "sign_governance_source":"native-trigger-and-approach",
             "sign_face_video_source":"front-and-overview",
             "native_stop_sign_id":17,
             "median_spacing_source":"native-roadway-openings",
             "same_statutory_crossing":True,
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]],
             "ego_approach_forward_xy":[1,0]}
        (root/"junction_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(ego,other) in enumerate((((0,0),(0,other_y)),((0,0),(12,0)),((12,0),(12,0)))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"governing_stop_sign_id":17,
                         "ego":vehicle(*ego,1),"other":vehicle(*other,2)})
        frames=[{"video_frame":i,"carla_frame":row["frame"],"time_s":row["time_s"]} for i,row in enumerate(rows)]
        (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_two_entries_right_side_and_elapsed_time_without_legal_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["other_spatially_right_of_ego_approach"])
            self.assertAlmostEqual(result["absolute_entry_time_difference_s"],.05)
            self.assertEqual(result["legal_conclusion"],"unresolved")
            self.fixture(root,10)
            self.assertFalse(measure.analyze(root)["other_spatially_right_of_ego_approach"])

    def test_wrong_sign_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(r) for r in (root/"crossing_history.jsonl").read_text().splitlines()]
            rows[2]["governing_stop_sign_id"]=999
            (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"sign identity mismatch"):
                measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                measure.analyze(root)


if __name__=="__main__":
    unittest.main()
