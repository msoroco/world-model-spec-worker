import importlib.util
import json
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


if __name__=="__main__":unittest.main()
