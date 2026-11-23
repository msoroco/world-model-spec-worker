import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("right_pass", ROOT / "right_pass.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def packet():
    controls = {v: {"source_id": v, "target_speed_mps": 8, "ego_speed_mps": 10,
                    "initial_body_gap_m": 8} for v in module.VARIANTS}
    controls["close_gap"]["initial_body_gap_m"] = 4
    controls["cross_traffic"]["cross_traffic_actor_pose_source"] = "native-conflict-pose"
    cross = [{"source": "native_map", "station_m": s,
              "right_lane_same_direction": True, "paved_y_bounds_m": [-4,4],
              "lane_centers_y_m": [1.7,-1.7]} for s in range(-30,31,5)]
    spawns = {v: {r: {"source_id": f"{v}-{r}", "blueprint_id": "vehicle.test",
                       "pose_xyz_ypr": [0,0,0,0,0,0]} for r in (("ego", "target", "conflict") if v == "cross_traffic" else ("ego", "target"))} for v in module.VARIANTS}
    return {"source_kind": "original_native_map_geometry", "source_id": "native-map-1",
            "paved_boundary_source": "native-pavement-1", "layout": "paved_road",
            "right_lane_same_direction": True, "pass_uses_shoulder": False,
            "max_actor_half_width_m": 0.8, "cross_sections": cross,
            "variant_controls": controls, "native_spawn": spawns}


def history():
    rows=[]
    for i, ego in enumerate((-8,-4,0,4,8)):
        rows.append({"frame": i, "time_s": i/20, "actor_ids": [1,2],
                     "ego_body_s_bounds_m": [ego-1,ego+1],
                     "target_body_s_bounds_m": [-1,1],
                     "ego_body_y_bounds_m": [-2.4,-0.8],
                     "target_body_y_bounds_m": [0.8,2.4],
                     "paved_y_bounds_m": [-4,4],
                     "ego_speed_mps": 10, "target_speed_mps": 8})
    return {"source_kind": "original_native_actor_history",
            "map_source_kind": "original_native_map_geometry",
            "map_sha256": "map-hash", "camera_profile": "four-camera-20hz",
            "actor_ids": [1,2], "samples": rows}


class Actor:
    def __init__(self, ident): self.id=ident; self.destroyed=False
    def get_transform(self): return object()
    def destroy(self): self.destroyed=True


class World:
    def __init__(self, fail_at=0): self.actors=[]; self.fail_at=fail_at
    def try_spawn_actor(self, _blueprint, _pose):
        if self.fail_at == len(self.actors)+1: return None
        a=Actor(len(self.actors)+1); self.actors.append(a); return a


class Library:
    def find(self, name): return name


class RightPassTests(unittest.TestCase):
    def test_all_variant_constructions(self):
        for variant in module.VARIANTS:
            self.assertEqual(module.construct(packet(), variant)["variant"], variant)

    def test_rejects_road_context_and_footprint(self):
        for key,value in (("right_lane_same_direction",False),("pass_uses_shoulder",True)):
            p=packet();p[key]=value
            with self.assertRaises(ValueError): module.construct(p,"open_gap")
        p=packet();p["cross_sections"][0]["paved_y_bounds_m"]=[-1,4]
        with self.assertRaises(ValueError): module.construct(p,"open_gap")

    def test_cross_traffic_requires_actor_pose(self):
        p=packet();del p["variant_controls"]["cross_traffic"]["cross_traffic_actor_pose_source"]
        with self.assertRaises(ValueError): module.construct(p,"cross_traffic")

    def test_native_spawn_and_cleanup(self):
        world=World()
        self.assertEqual(len(module.spawn_native(world,Library(),packet(),"cross_traffic",lambda p:p)["actors"]),3)
        world=World(fail_at=2)
        with self.assertRaises(ValueError): module.spawn_native(world,Library(),packet(),"open_gap",lambda p:p)
        self.assertTrue(world.actors[0].destroyed)

    def test_whole_pass_measurement(self):
        x=module.measure(history())
        self.assertEqual(x["passing_frames"],[2])
        self.assertEqual(x["minimum_lateral_body_clearance_m"],1.6)
        self.assertEqual(x["legal_safety_judgment"],"unresolved")

    def test_conflict_body_is_measured(self):
        h=history();h["actor_ids"]=[1,2,3]
        for row in h["samples"]:
            row["actor_ids"]=[1,2,3]
            row["conflict_body_s_bounds_m"]=[0,2]
            row["conflict_body_y_bounds_m"]=[-3.2,-2.8]
        self.assertAlmostEqual(module.measure(h)["minimum_conflict_body_distance_m"],0.4)
        del h["samples"][2]["conflict_body_y_bounds_m"]
        with self.assertRaises(KeyError): module.measure(h)

    def test_measure_rejects_missing_phases_and_sources(self):
        h=history();h["samples"]=h["samples"][:3]
        with self.assertRaises(ValueError): module.measure(h)
        h=history();h["samples"][2]["time_s"]=0.2
        with self.assertRaises(ValueError): module.measure(h)
        h=history();h["samples"][2]["ego_body_y_bounds_m"]=[0,1.6]
        with self.assertRaises(ValueError): module.measure(h)
        h=history();h["source_kind"]="synthetic_summary"
        with self.assertRaises(ValueError): module.measure(h)

    def test_sealed_finalizer_and_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"history.json";out=Path(d)/"facts.json"
            source.write_text(json.dumps(history()),encoding="utf-8")
            sha=hashlib.sha256(source.read_bytes()).hexdigest()
            result=module.finalize_sealed(source,sha,out)
            self.assertEqual(result["source_sha256"],sha)
            with self.assertRaises(ValueError): module.finalize_sealed(source,"0"*64,Path(d)/"bad.json")
        a={"map_sha256":"map","camera_profile":"four","duration_s":45,
           "primary_actor_blueprints":["car","car"],"paved_boundary_source":"pavement",
           "source_sha256":"a","measurement":{"minimum_approach_body_gap_m":5,"conflict_actor_present":False}}
        b=copy.deepcopy(a);b["source_sha256"]="b";b["measurement"]["minimum_approach_body_gap_m"]=3
        module.audit_comparison(a,b,"minimum_approach_body_gap_m")
        b["map_sha256"]="other"
        with self.assertRaises(ValueError): module.audit_comparison(a,b,"minimum_approach_body_gap_m")


if __name__ == "__main__": unittest.main()
