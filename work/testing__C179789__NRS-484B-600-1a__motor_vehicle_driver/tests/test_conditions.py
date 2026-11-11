import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


measure=load("conditions_measurements")
traffic=load("traffic_construction")


class ConditionsTests(unittest.TestCase):
    def fixture(self,root,surface="dry",sight=15):
        ctx={"native_map_id":"TownX","ego_actor_id":10,"road_id":7,"lane_id":-1,
             "road_surface_source":"native-map-and-original-camera",
             "lane_width_source":"native-waypoint-and-road-boundary",
             "traffic_source":"native-actor-body-and-video",
             "weather_source":"native-weather-readback",
             "sight_source":"native-rays-original-frame",
             "curvature_source":"native-waypoint-chain",
             "braking_model_source":"declared-5mps2-diagnostic",
             "diagnostic_reaction_time_s":1.0,
             "diagnostic_braking_deceleration_mps2":5.0}
        (root/"road_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i in range(2):
            rows.append({"frame":100+i,"time_s":1+i*.05,"ego_actor_id":10,
                         "road_id":7,"lane_id":-1,"ego_velocity_source":"actor.get_velocity",
                         "ego_velocity_mps":[10,0,0],"lane_width_m":3.2,
                         "surface":surface,"precipitation_percent":0 if surface=="dry" else 80,
                         "sight_distance_m":sight,"curvature_per_m":.002,
                         "surrounding_traffic":[{"actor_id":20,"velocity_source":"actor.get_velocity",
                                                 "velocity_mps":[5,0,0],"longitudinal_body_gap_m":20}]})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"condition_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_frame_specific_conditions_and_nonlegal_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            dry=measure.analyze(root)
            self.assertEqual(dry["samples"][0]["diagnostic_stopping_distance_m"],20)
            self.assertTrue(dry["samples"][0]["diagnostic_stop_distance_exceeds_sight"])
            self.assertFalse(dry["engineering_model"]["legal_threshold"])
            self.assertEqual(dry["legal_conclusion"],"unresolved")
            self.fixture(root,"wet",25)
            wet=measure.analyze(root)
            self.assertEqual(wet["samples"][0]["surface"],"wet")
            self.assertFalse(wet["samples"][0]["diagnostic_stop_distance_exceeds_sight"])

    def test_missing_traffic_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(r) for r in (root/"condition_history.jsonl").read_text().splitlines()]
            del rows[1]["surrounding_traffic"]
            (root/"condition_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"traffic inventory"):measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)

    def test_native_lead_spawn_gap_and_cleanup(self):
        destroyed=[]
        ego=NS(get_location=lambda:NS(x=0,y=0),bounding_box=NS(extent=NS(x=2)))
        lead=NS(get_location=lambda:NS(x=20,y=0),bounding_box=NS(extent=NS(x=2)),
                destroy=lambda:destroyed.append(True))
        native_map=NS(get_waypoint=lambda location,project_to_road:NS(road_id=7,lane_id=-1))
        world=NS(try_spawn_actor=lambda blueprint,transform:lead,get_map=lambda:native_map)
        with traffic.spawn_lead_traffic(world,ego,"blueprint","transform",7,-1,(1,0)) as built:
            self.assertEqual(built["initial_longitudinal_body_gap_m"],16)
        self.assertEqual(destroyed,[True])


if __name__=="__main__":unittest.main()
