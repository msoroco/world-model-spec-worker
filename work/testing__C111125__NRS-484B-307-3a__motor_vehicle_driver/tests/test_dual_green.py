import hashlib
import importlib.util
import importlib
import json
import tempfile
import unittest
import sys
import io
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded

green = importlib.import_module("dual_green")
compare = module("comparison_audit")
native = module("native_attempt")
saved = module("saved_attempt")
finalizer = module("saved_finalizer")
cameras = module("camera_audit")


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

    def test_dual_green_must_start_before_and_span_ego_entry(self):
        event_ref = self.event_ref()
        path = self.root / event_ref["path"]
        rows = json.loads(path.read_text())
        rows[0]["lit_aspects"] = ["circular_green"]
        path.write_text(json.dumps(rows))
        event_ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(green.EvidenceError, "after ego entered"):
            green.measure_original(self.site, self.root, event_ref)

        rows[0]["lit_aspects"] = ["circular_green", "green_left_arrow"]
        rows[1]["lit_aspects"] = ["circular_green"]
        path.write_text(json.dumps(rows))
        event_ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(green.EvidenceError, "does not span ego entry"):
            green.measure_original(self.site, self.root, event_ref)

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

    def native_fixture(self, other=False, with_cameras=False):
        class Actor:
            def __init__(self, actor_id, x, y):
                self.id = actor_id
                self.x, self.y = x, y
            def get_location(self):
                return type("Location", (), {"x": self.x, "y": self.y})()
        ego = Actor(1, -10, 0)
        actors = [ego]
        if other:
            actors.append(Actor(2, 0, 4))
            self.site["other_user_kind"] = "pedestrian"
        class World:
            frame = 9
            def get_settings(self):
                return type("Settings", (), {"synchronous_mode": True, "fixed_delta_seconds": .05})()
            def tick(self):
                self.frame += 1
                return self.frame
            def get_snapshot(self):
                return type("Snapshot", (), {"frame": self.frame,
                        "timestamp": type("Timestamp", (), {"elapsed_seconds": self.frame * .05})()})()
        def ref_for(prefix, frame, content):
            path = self.root / f"{prefix}-{frame}.json"
            path.write_text(json.dumps(content))
            return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        lamps = {}
        lawful = {}
        for frame in (10, 11, 12):
            lamps[frame] = ref_for("lamp", frame, {"frame": frame, "official_head_id": "5",
                "facing_approach_id": "east", "lit_aspects": ["circular_green", "green_left_arrow"]})
            if other:
                lawful[frame] = ref_for("lawful", frame, {"frame": frame, "user_id": "2", "review": "pending"})
        def controller(actor, index):
            actor.x = (-10, 0, 10)[index]
        case_id = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__dual_pedestrian_present" if other else "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__dual_clear"
        attempt = self.root / "attempt"
        camera_callback = None
        if with_cameras:
            image = Image.new("RGB", (2, 2), (1, 2, 3))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            payload = buffer.getvalue()
            camera_callback = lambda frame: {name: payload for name in cameras.CAMERAS}
        receipt = native.run_native_attempt(self.site, self.root, World(), actors, controller,
            lambda frame: lamps[frame], lambda frame, user_id: lawful[frame], attempt, case_id, 3,
            camera_frame_for_tick=camera_callback)
        return attempt, case_id, receipt

    def test_four_camera_source_decode_and_join(self):
        attempt, case_id, receipt = self.native_fixture(with_cameras=True)
        self.assertIn("camera_manifest_source", receipt)
        audited = cameras.audit_cameras(attempt, case_id,
                                        dimensions={name: (2, 2) for name in cameras.CAMERAS},
                                        expected_frames=3)
        self.assertEqual(audited["camera_frames_decoded"], 12)
        self.assertFalse(audited["physical_visibility_confirmed"])

    def test_four_camera_rejects_missing_and_corrupt_source(self):
        attempt, case_id, _ = self.native_fixture(with_cameras=True)
        image = attempt / "original-overview-000001.png"
        image.unlink()
        with self.assertRaisesRegex(green.EvidenceError, "missing or escaping"):
            cameras.audit_cameras(attempt, case_id,
                                  dimensions={name: (2, 2) for name in cameras.CAMERAS},
                                  expected_frames=3)

    def test_four_camera_rejects_frame_map_rebinding(self):
        attempt, case_id, receipt = self.native_fixture(with_cameras=True)
        path = attempt / "original-cameras.json"
        manifest = json.loads(path.read_text())
        manifest["frames"][1]["carla_frame"] = 99
        path.write_text(json.dumps(manifest))
        receipt["camera_manifest_source"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (attempt / "native-attempt.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(green.EvidenceError, "camera frame map mismatch"):
            cameras.audit_cameras(attempt, case_id,
                                  dimensions={name: (2, 2) for name in cameras.CAMERAS},
                                  expected_frames=3)

    def test_delivery_requires_full_duration(self):
        attempt, case_id, _ = self.native_fixture(with_cameras=True)
        with self.assertRaisesRegex(green.EvidenceError, "camera duration mismatch"):
            saved.measure_delivery(self.site, self.root, attempt, case_id)

    def test_diagnostic_finalizer_retains_exact_source_hashes(self):
        attempt, case_id, receipt = self.native_fixture(with_cameras=True)
        site_path = self.root / "site.json"
        site_path.write_text(json.dumps(self.site))
        output = self.root / "observation.json"
        report = finalizer.finalize(site_path, self.root, attempt, case_id, output,
                                    diagnostic=True)
        self.assertTrue(report["diagnostic_only"])
        self.assertEqual(report["event_sha256"], receipt["event_source"]["sha256"])
        self.assertEqual(report["site_sha256"], hashlib.sha256(site_path.read_bytes()).hexdigest())
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertIsNone(report["permission_verdict"])
        self.assertEqual(json.loads(output.read_text()), report)

    def test_finalizer_rejects_short_production_and_missing_original(self):
        attempt, case_id, _ = self.native_fixture(with_cameras=True)
        site_path = self.root / "site.json"
        site_path.write_text(json.dumps(self.site))
        output = self.root / "observation.json"
        with self.assertRaisesRegex(green.EvidenceError, "camera duration mismatch"):
            finalizer.finalize(site_path, self.root, attempt, case_id, output)
        self.assertFalse(output.exists())
        (attempt / "original-events.json").unlink()
        with self.assertRaisesRegex(green.EvidenceError, "missing or escaping"):
            finalizer.finalize(site_path, self.root, attempt, case_id, output,
                               diagnostic=True)

    def test_native_attempt_and_saved_source_join(self):
        attempt, case_id, receipt = self.native_fixture(other=True)
        self.assertEqual(receipt["sample_hz"], 20)
        measured = saved.measure_saved(self.site, self.root, attempt, case_id)
        self.assertEqual(measured["frame_count"], 3)
        self.assertEqual(measured["exhibition"]["other_users"][0]["region"], "adjacent_crosswalk")
        self.assertIsNone(measured["right_of_way_verdict"])

    def test_saved_rejects_case_observation_mismatch(self):
        attempt, _, _ = self.native_fixture(other=True)
        wrong_case = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__dual_clear"
        receipt_path = attempt / "native-attempt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["case_id"] = wrong_case
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(green.EvidenceError, "clear case has another user"):
            saved.measure_saved(self.site, self.root, attempt, wrong_case)

    def test_late_pedestrian_requires_observed_crosswalk_entry(self):
        case_id = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__dual_pedestrian_late"
        outside = {"id": "walk-1", "kind": "pedestrian", "region": "outside"}
        measured = {"exhibition": {"frame": 10, "other_users": [outside]},
                    "records": [{"frame": 10, "other_users": [outside]},
                                {"frame": 11, "other_users": [outside]}]}
        with self.assertRaisesRegex(green.EvidenceError, "never entered"):
            saved.check_case_observation(case_id, measured)
        measured["records"][1]["other_users"] = [dict(outside, region="adjacent_crosswalk")]
        self.assertEqual(saved.check_case_observation(case_id, measured)["case_suffix"],
                         "dual_pedestrian_late")

    def test_present_case_rejects_wrong_kind_or_region(self):
        case_id = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__dual_vehicle_present"
        measured = {"exhibition": {"frame": 10, "other_users": [
            {"id": "2", "kind": "pedestrian", "region": "intersection"}]},
                    "records": [{"frame": 10, "other_users": [
                        {"id": "2", "kind": "pedestrian", "region": "intersection"}]}]}
        with self.assertRaisesRegex(green.EvidenceError, "contrast not observed"):
            saved.check_case_observation(case_id, measured)
        measured["exhibition"]["other_users"][0]["kind"] = "motor_vehicle"
        measured["records"][0]["other_users"][0]["kind"] = "motor_vehicle"
        self.assertEqual(saved.check_case_observation(case_id, measured)["case_suffix"],
                         "dual_vehicle_present")

    def test_saved_contrast_rejects_participant_swap_and_late_clear_user(self):
        prefix = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
        user = {"id": "2", "kind": "motor_vehicle", "region": "intersection"}
        exhibition = {"frame": 10, "other_users": [user]}
        measured = {"exhibition": exhibition, "records": [exhibition,
                    {"frame": 11, "other_users": [dict(user, id="3")]}]}
        with self.assertRaisesRegex(green.EvidenceError, "identity or kind changed"):
            saved.check_case_observation(prefix + "dual_vehicle_present", measured)
        measured["records"][1]["other_users"] = [user]
        self.assertEqual(saved.check_case_observation(prefix + "dual_vehicle_present", measured)
                         ["case_suffix"], "dual_vehicle_present")
        empty = {"frame": 10, "other_users": []}
        measured = {"exhibition": empty, "records": [empty,
                    {"frame": 11, "other_users": [user]}]}
        with self.assertRaisesRegex(green.EvidenceError, "clear case has another user"):
            saved.check_case_observation(prefix + "dual_clear", measured)
        with self.assertRaisesRegex(green.EvidenceError, "wrong exact dual-green assignment"):
            saved.check_case_observation("other__dual_clear", measured)

    def test_saved_rejects_lamp_mutation_and_wrong_case(self):
        attempt, case_id, _ = self.native_fixture()
        with self.assertRaisesRegex(green.EvidenceError, "attempt case mismatch"):
            saved.measure_saved(self.site, self.root, attempt, case_id + "_wrong")
        (self.root / "lamp-11.json").write_text("{}")
        with self.assertRaisesRegex(green.EvidenceError, "hash mismatch"):
            saved.measure_saved(self.site, self.root, attempt, case_id)

    def test_saved_rejects_event_mutation_and_missing_frame(self):
        attempt, case_id, _ = self.native_fixture()
        event = attempt / "original-events.json"
        rows = json.loads(event.read_text())
        rows.pop()
        event.write_text(json.dumps(rows))
        with self.assertRaisesRegex(green.EvidenceError, "hash mismatch"):
            saved.measure_saved(self.site, self.root, attempt, case_id)

    def test_native_rejects_wrong_lamp_packet(self):
        attempt, case_id, _ = self.native_fixture()
        class NoTick:
            def get_settings(self):
                return type("Settings", (), {"synchronous_mode": False, "fixed_delta_seconds": .05})()
        with self.assertRaisesRegex(green.EvidenceError, "synchronous"):
            native.run_native_attempt(self.site, self.root, NoTick(), [object()], lambda *_: None,
                lambda *_: None, lambda *_: None, attempt, case_id, 3)


if __name__ == "__main__":
    unittest.main()
