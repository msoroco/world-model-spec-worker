import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded

green = module("dual_green")
compare = module("comparison_audit")


class DualGreenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        names = ["map", "route", "signal", "crosswalk", "permission"]
        refs = []
        for name in names:
            p = self.root / (name + ".json")
            p.write_text(json.dumps({"original": name}))
            refs.append({"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        self.site = {
            "cell_id": "C111125", "actor": "motor_vehicle_driver", "original_sources": refs,
            "map_source_path": refs[0]["path"], "route_source_path": refs[1]["path"],
            "signal_survey_path": refs[2]["path"], "crosswalk_source_path": refs[3]["path"],
            "movement_permission_source_path": refs[4]["path"],
            "official_head_id": "5", "ego_approach_id": "east", "facing_relation": True,
            "arrow_direction": "left", "ego_movement": "straight", "straight_permission_review": "source_review_pending",
            "ego_route_xy": [[-10, 0], [0, 0], [10, 0]], "straight_tolerance_m": 0.2,
            "intersection_polygon_xy": [[-2,-2],[2,-2],[2,2],[-2,2]],
            "adjacent_crosswalk_polygon_xy": [[-4,3],[4,3],[4,5],[-4,5]],
            "native_map_name": "TownSurvey", "spawn_z_m": 0.5, "approach_yaw_deg": 0,
            "other_user_spawn_xy": [0, 4],
        }

    def event_ref(self, aspects=None, other=None):
        aspects = aspects if aspects is not None else ["circular_green", "green_left_arrow"]
        rows = []
        for frame, ego in enumerate(([-10,0], [0,0], [10,0])):
            rows.append({"frame": frame, "official_head_id": "5", "facing_approach_id": "east",
                         "aspect_observation_source": "original/lamp_observer.json", "lit_aspects": aspects,
                         "ego_xy": ego, "other_users": other or []})
        p = self.root / "events.json"
        p.write_text(json.dumps(rows))
        return {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

    def test_original_dual_aspect_and_crossing(self):
        measured = green.measure_original(self.site, self.root, self.event_ref())
        self.assertTrue(measured["exhibition"]["dual_green"])
        self.assertTrue(measured["records"][1]["ego_in_intersection"])
        self.assertIsNone(measured["right_of_way_verdict"])

    def test_circular_green_alone_rejected(self):
        with self.assertRaisesRegex(green.EvidenceError, "no simultaneous"):
            green.measure_original(self.site, self.root, self.event_ref(["circular_green"]))

    def test_wrong_arrow_rejected(self):
        with self.assertRaisesRegex(green.EvidenceError, "no simultaneous"):
            green.measure_original(self.site, self.root, self.event_ref(["circular_green", "green_right_arrow"]))

    def test_source_mutation_rejected(self):
        (self.root / "signal.json").write_text("changed")
        with self.assertRaisesRegex(green.EvidenceError, "hash mismatch"):
            green.check_site(self.site, self.root)

    def test_lawful_use_source_required(self):
        user = {"id": "walk-1", "kind": "pedestrian", "xy": [0,4]}
        with self.assertRaisesRegex(green.EvidenceError, "lawful-use"):
            green.measure_original(self.site, self.root, self.event_ref(other=[user]))

    def test_route_turn_rejected(self):
        self.site["ego_route_xy"][1] = [0,3]
        with self.assertRaisesRegex(green.EvidenceError, "route bends"):
            green.check_site(self.site, self.root)

    def test_native_construction_readback_and_cleanup(self):
        class Head:
            id = 5
            def get_state(self):
                return type("State", (), {"name": "Green"})()
        class Actors:
            def filter(self, _):
                return [Head()]
        class Actor:
            def __init__(self):
                self.destroyed = False
            def destroy(self):
                self.destroyed = True
        ego = Actor()
        class World:
            def get_map(self):
                return type("Map", (), {"name": "TownSurvey"})()
            def get_actors(self):
                return Actors()
            def try_spawn_actor(self, blueprint, _):
                return ego if blueprint == "ego" else None
        class Carla:
            @staticmethod
            def Location(**fields):
                return fields
            @staticmethod
            def Rotation(**fields):
                return fields
            @staticmethod
            def Transform(location, rotation):
                return (location, rotation)
        result = green.construct_native(self.site, self.root, World(), Carla, "ego")
        self.assertEqual(len(result["actors"]), 1)
        self.assertFalse(result["dual_aspect_proven"])
        with self.assertRaisesRegex(green.EvidenceError, "other user spawn failed"):
            green.construct_native(self.site, self.root, World(), Carla, "ego", "person", "pedestrian")
        self.assertTrue(ego.destroyed)

    def summary(self, suffix, users):
        return {"case_suffix": suffix, "map_sha256": "a", "route_sha256": "b", "signal_survey_sha256": "c",
                "crosswalk_sha256": "d", "movement_permission_sha256": "e", "camera_profile_sha256": "f",
                "duration_frames": 2, "official_head_id": "5", "ego_approach_id": "east", "arrow_direction": "left",
                "records": [{"dual_green": True}, {"dual_green": True}],
                "exhibition": {"other_users": [{"region": x} for x in users]},
                "permission_verdict": None, "right_of_way_verdict": None}

    def test_comparison_positive_and_negative(self):
        clear = self.summary("dual_clear", [])
        walker = self.summary("dual_pedestrian_present", ["adjacent_crosswalk"])
        self.assertEqual(compare.audit_pair("pedestrian_at_exhibition", clear, walker)["source_frames_checked"], 4)
        walker["arrow_direction"] = "right"
        with self.assertRaisesRegex(compare.ComparisonError, "fixed condition"):
            compare.audit_pair("pedestrian_at_exhibition", clear, walker)

    def test_comparison_rejects_missing_aspect_and_verdict(self):
        clear = self.summary("dual_clear", [])
        vehicle = self.summary("dual_vehicle_present", ["intersection"])
        vehicle["records"][0]["dual_green"] = False
        with self.assertRaisesRegex(compare.ComparisonError, "simultaneous"):
            compare.audit_pair("vehicle_at_exhibition", clear, vehicle)
        vehicle["records"][0]["dual_green"] = True
        vehicle["right_of_way_verdict"] = "yielded"
        with self.assertRaisesRegex(compare.ComparisonError, "unsupported legal"):
            compare.audit_pair("vehicle_at_exhibition", clear, vehicle)


if __name__ == "__main__":
    unittest.main()
