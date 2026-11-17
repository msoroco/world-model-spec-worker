import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_pair import step_pair
from test_median_route_control import scene
from test_native_pair import Actor
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

    def test_original_body_entry_timing_landmarks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            observed=[]
            for other_entry_index in (1,2,3):
                rows=[]
                for i in range(5):
                    rows.append({"frame":100+i,"time_s":1+i*.05,
                                 "governing_stop_sign_id":17,
                                 "ego":vehicle(12 if i>=2 else 0,0,1),
                                 "other":vehicle(12 if i>=other_entry_index else 0,
                                                 0 if i>=other_entry_index else -10,2)})
                frames=[{"video_frame":i,"carla_frame":row["frame"],
                         "time_s":row["time_s"]} for i,row in enumerate(rows)]
                (root/"crossing_history.jsonl").write_text(
                    "".join(json.dumps(row)+"\n" for row in rows))
                (root/"video_frames.jsonl").write_text(
                    "".join(json.dumps(row)+"\n" for row in frames))
                result=measure.analyze(root)
                self.assertEqual(result["legal_conclusion"],"unresolved")
                observed.append((result["first_body_entry"]["ego"]["frame"],
                                 result["first_body_entry"]["other"]["frame"],
                                 round(result["absolute_entry_time_difference_s"],2)))
            self.assertEqual(observed,[(102,101,.05),(102,102,0),(102,103,.05)])

    def test_exact_release_setpoints_feed_original_shaped_entry_measurement(self):
        # A simple kinetic CPU surrogate checks the control-to-source wiring.
        # It is deliberately not a claim about CARLA vehicle dynamics.
        carla=NS(VehicleControl=lambda:NS())
        observed=[]
        for release_frame in (32,40,48):
            ego,other=Actor(8,0,speed=.05),Actor(15,-15,speed=0)
            progress={'ego':1,'other':1};stopped=False;rows=[]
            for i in range(135):
                progress,stopped,commands=step_pair(
                    carla,ego,other,scene(),progress,stopped,i>=80,
                    i>=release_frame)
                for role,actor in (('ego',ego),('other',other)):
                    command=commands[role]
                    speed=math.hypot(actor.velocity.x,actor.velocity.y)
                    speed=max(0,min(5,speed+1.5*command['throttle']
                                    -2*command['brake']))
                    if role=='ego':
                        actor.velocity.x=speed
                        actor.pose.location.x+=speed*.05
                    else:
                        actor.velocity.y=speed
                        actor.pose.location.y+=speed*.05
                rows.append({'frame':1000+i,'time_s':i*.05,
                             'governing_stop_sign_id':17,
                             'ego':vehicle(ego.pose.location.x,0,1),
                             'other':vehicle(15,other.pose.location.y,2)})
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.fixture(root)
                context=json.loads((root/'junction_context.json').read_text())
                context['intersection_polygon_xy_m']=scene()['crossing_polygon_xy_m']
                (root/'junction_context.json').write_text(json.dumps(context))
                frames=[{'video_frame':i,'carla_frame':row['frame'],
                         'time_s':row['time_s']} for i,row in enumerate(rows)]
                (root/'crossing_history.jsonl').write_text(
                    ''.join(json.dumps(row)+'\n' for row in rows))
                (root/'video_frames.jsonl').write_text(
                    ''.join(json.dumps(row)+'\n' for row in frames))
                result=measure.analyze(root)
                self.assertEqual(result['legal_conclusion'],'unresolved')
                observed.append((release_frame,
                                 result['first_body_entry']['ego']['frame'],
                                 result['first_body_entry']['other']['frame']))
        self.assertEqual(observed,[(32,1087,1079),(40,1087,1087),
                                   (48,1087,1095)])

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

    def test_opposite_left_turn_exception_is_measured_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/"junction_context.json").read_text())
            ctx.update({"approach_relation":"opposite_directions",
                        "other_highway_id":"east-west",
                        "other_approach_forward_xy":[-1,0],
                        "turn_intent_source":"original-turn-indicator-and-route-history"})
            (root/"junction_context.json").write_text(json.dumps(ctx))
            rows=[json.loads(line) for line in (root/"crossing_history.jsonl").read_text().splitlines()]
            for row in rows:row["other_left_turn_intended"]=True
            rows[0]["other"]["body_vertices_xy_m"]=[[x+30,y] for x,y in ((-1,-1),(-1,1),(1,1),(1,-1))]
            (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            result=measure.analyze(root)
            self.assertEqual(result["approach_relation"],"opposite_directions")
            self.assertIsNone(result["other_spatially_right_of_ego_approach"])
            self.assertEqual(result["opposite_direction_left_turn_exception_judgment"],"unresolved")
            rows[1]["other_left_turn_intended"]=False
            (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"left-turn intention missing"):
                measure.analyze(root)
            rows[1]["other_left_turn_intended"]=True
            rows[0]["other"]["body_vertices_xy_m"]=[[x,y-10] for x,y in ((-1,-1),(-1,1),(1,1),(1,-1))]
            (root/"crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"approach does not match heading"):
                measure.analyze(root)


if __name__=="__main__":
    unittest.main()
