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
control_spec=importlib.util.spec_from_file_location("signal_control",ROOT/"signal_control.py")
control=importlib.util.module_from_spec(control_spec)
control_spec.loader.exec_module(control)


def vehicle(x,y,road):
    return {"intersection_id":44,"road_id":road,
            "body_vertices_xy_m":[[x+dx,y+dy] for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1))]}


class EntryTests(unittest.TestCase):
    def test_native_two_entrance_signal_off_and_restore(self):
        class Light:
            def __init__(self,identifier,road):self.id,self.road,self.state=identifier,road,"Green"
            def get_affected_lane_waypoints(self):return [NS(road_id=self.road,lane_id=-1)]
            def get_state(self):return self.state
            def set_state(self,value):self.state=value
            def freeze(self,value):self.frozen=value
        class Actors(list):
            def filter(self,pattern):return self
        a,b=Light(17,1),Light(18,2)
        world=NS(get_actors=lambda:Actors([a,b]),tick=lambda:None)
        selected=control.find_entrance_lights(world,[(1,-1),(2,-1)])
        with control.request_all_off(world,selected,NS(Off="Off")):
            self.assertEqual((a.state,b.state),("Off","Off"))
        self.assertEqual((a.state,b.state),("Green","Green"))
        self.assertFalse(a.frozen or b.frozen)

    def fixture(self,root,other_y=-10):
        ctx={"native_map_id":"TownX","intersection_id":44,
             "ego_highway_id":"east-west","other_highway_id":"north-south",
             "ego_road_id":1,"other_road_id":2,
             "crossing_geometry_source":"native-and-original-camera",
             "all_entrances_source":"native-lane-inventory",
             "signal_governance_source":"native-affected-waypoints",
             "signal_head_video_source":"front-and-overview",
             "median_spacing_source":"native-roadway-openings",
             "same_statutory_crossing":True,
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]],
             "ego_approach_forward_xy":[1,0]}
        (root/"junction_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,(ego,other) in enumerate((((0,0),(0,other_y)),((0,0),(12,0)),((12,0),(12,0)))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"governing_signal_state":"Off",
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

    def test_boundary_contact_precedes_complete_body_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(r) for r in (root/"crossing_history.jsonl").read_text().splitlines()]
            rows[1]["other"]=vehicle(9,0,2)
            (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            result=measure.analyze(root)
            self.assertEqual(result["first_body_entry"]["other"]["frame"],102)
            self.assertEqual(result["first_body_entry"]["ego"]["frame"],102)

    def test_operative_signal_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(r) for r in (root/"crossing_history.jsonl").read_text().splitlines()]
            rows[2]["governing_signal_state"]="Green"
            (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"not observed Off"):
                measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                measure.analyze(root)


if __name__=="__main__":
    unittest.main()
