import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("blind_signal_measurements")
construction = load("occluder_construction")
signals = load("signal_control")


def vehicle(x, speed, signed):
    return {"intersection_id": 44, "speed_mps": speed,
            "front_to_stop_line_signed_m": signed,
            "body_vertices_xy_m": [[x+dx, y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]}


class BlindSignalTests(unittest.TestCase):
    def test_all_entrance_native_off_request_and_restore(self):
        class Light:
            def __init__(self, identifier, road_id):
                self.id, self.road_id, self.state = identifier, road_id, "Green"
                self.frozen = False
            def get_affected_lane_waypoints(self):
                return [NS(road_id=self.road_id,lane_id=-1)]
            def get_state(self):
                return self.state
            def set_state(self, value):
                self.state = value
            def freeze(self, value):
                self.frozen = value
        class Actors(list):
            def filter(self, pattern):
                self.pattern = pattern
                return self
        a,b=Light(17,7),Light(18,9)
        ticks=[]
        world=NS(get_actors=lambda:Actors([a,b]),tick=lambda:ticks.append(True))
        selected=signals.find_entrance_lights(world,[(7,-1),(9,-1)])
        with signals.request_all_off(world,selected,NS(Off="Off")):
            self.assertEqual((a.get_state(),b.get_state()),("Off","Off"))
        self.assertEqual((a.get_state(),b.get_state()),("Green","Green"))
        self.assertFalse(a.frozen or b.frozen)
        self.assertEqual(len(ticks),2)

    def fixture(self, root):
        ctx = {"native_map_id":"TownX", "intersection_id":44,
               "signal_head_video_source":"front-and-overview-original",
               "all_entrances_source":"native-lane-inventory",
               "stop_line_source":"map-and-front-original",
               "occluder_geometry_source":"native-body-vertices",
               "sight_ray_source":"native-ray-samples", "stop_line_exists":True,
               "signal_heads":[{"native_id":17,"entrance_id":"west","installed":True,"uncovered":True},
                               {"native_id":18,"entrance_id":"south","installed":True,"uncovered":True}],
               "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"junction_context.json").write_text(json.dumps(ctx))
        positions = [(0,0,0),(0,0,0),(0,0,12),(12,0,12)]
        rows = []
        for i,(ego_x,earlier_x,occupant_x) in enumerate(positions):
            rows.append({"frame":100+i,"time_s":1+i*.05,
                         "signal_states":{"17":"Off","18":"Off"},
                         "ego":vehicle(ego_x,0 if i == 1 else 2,2 if i == 1 else -1),
                         "earlier":vehicle(earlier_x,0,2),
                         "occupant":vehicle(occupant_x,1,-1)})
        frames=[{"video_frame":i,"carla_frame":row["frame"],"time_s":row["time_s"]}
                for i,row in enumerate(rows)]
        (root/"vehicle_signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_three_distinct_histories_and_all_heads_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=measure.analyze(root)
            self.assertTrue(result["ego_stopped_before_entry_observed"])
            self.assertTrue(result["distinct_other_stopped_earlier_observed"])
            self.assertTrue(result["distinct_occupant_inside_at_ego_entry_observed"])
            self.assertEqual(result["legal_conclusion"],"unresolved")

    def test_operative_head_and_stale_video_join_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            rows=[json.loads(s) for s in (root/"vehicle_signal_history.jsonl").read_text().splitlines()]
            rows[-1]["signal_states"]["18"]="Green"
            (root/"vehicle_signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"all.*Off|All governing heads"):
                measure.analyze(root)
            self.fixture(root)
            frames=[json.loads(s) for s in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                measure.analyze(root)

    def test_realized_occluder_crosses_both_approach_rays_and_cleans_up(self):
        points=[NS(x=x,y=y) for x,y in ((4,-1),(4,1),(6,1),(6,-1))]
        destroyed=[]
        actor=NS(bounding_box=NS(get_world_vertices=lambda transform:points),
                 get_transform=lambda:"transform",destroy=lambda:destroyed.append(True))
        world=NS(try_spawn_actor=lambda blueprint, transform:actor)
        rays={"ego":(NS(x=0,y=0),NS(x=10,y=0)),
              "other":(NS(x=0,y=0.5),NS(x=10,y=0.5))}
        with construction.spawn_verified_occluder(world,"blueprint","spawn",rays) as realized:
            self.assertEqual(realized["approach_ray_intersections"],{"ego":True,"other":True})
        self.assertEqual(destroyed,[True])
        rays["other"]=(NS(x=0,y=3),NS(x=10,y=3))
        with self.assertRaisesRegex(ValueError,"both approach rays"):
            with construction.spawn_verified_occluder(world,"blueprint","spawn",rays):
                pass
        self.assertEqual(destroyed,[True,True])


if __name__ == "__main__":
    unittest.main()
