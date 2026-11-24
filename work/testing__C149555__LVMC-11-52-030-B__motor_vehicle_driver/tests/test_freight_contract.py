import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "freight_contract.py"
spec = importlib.util.spec_from_file_location("freight_contract", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def site():
    return {"cell_id": "C149555", "layout": "one_way_road", "control": "yellow_curb",
            "native_map_sha256": "map-seal", "native_road_id": 2, "native_lane_id": -1,
            "curb_observation_sha256": "curb-seal", "sign_observation_sha256": "sign-seal",
            "curb_color_observed": "yellow", "sign_text_observed": "Freight 8-18",
            "posted_conditions": {"verbatim_text": "Freight 8-18", "civil_windows": ["08-18"], "freight_permitted": True},
            "zone": {"start_station_m": 20, "end_station_m": 40},
            "approach_station_m": 5, "outside_station_m": 60,
            "one_way_native_readback": True, "freight_prop_blueprint": "prop.cargo"}


class Adapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            return {"spawn_or_verify_sign": "sign-1", "spawn_vehicle": "ego-1", "spawn_freight": "cargo-1"}.get(name)
        return call


def packet(variant="freight_loading"):
    return {"case_id": "case", "variant": variant, "native_result_sha256": "r", "frame_map_sha256": "f",
            "native_map_sha256": "m", "curb_observation_sha256": "c", "sign_observation_sha256": "s",
            "commercial_dossier_sha256": "d", "freight_activity_source_sha256": "a",
            "curb_color_observed": "yellow", "one_way_native_readback": True,
            "native_map_readback": {"native_road_id": 2, "native_lane_id": -1, "one_way_native_readback": True},
            "curb_observation": {"start_station_m": 20, "end_station_m": 40, "independent_pixel_review": True},
            "sign_observation": {"independent_pixel_review": True},
            "sign_text_readback": "Freight 8-18", "posted_conditions": {"verbatim_text": "Freight 8-18"},
            "vehicle_id": "truck-1", "commercial_dossier": {"vehicle_id": "truck-1", "enterprise_use_reviewed": True, "qualifies_commercial": True},
            "frames": [{"original_frame": i, "time_s": i / 20, "ego_station_m": 30,
                        "ego_body_station_min_m": 28, "ego_body_station_max_m": 32,
                        "ego_speed_mps": 0.0} for i in range(900)],
            "zone": {"start_station_m": 20, "end_station_m": 40},
            "freight_activity": {"vehicle_id": "truck-1", "observed_action": "loading", "cargo_actor_id": "cargo-1", "observed_transfer_frames": [50, 51]},
            "civil_time": {"source_sha256": "clock", "timezone": "America/Los_Angeles", "local_datetime": "2026-11-23T12:00:00"},
            "posted_window_check": {"source_sha256": "window", "derived_from_sign_sha256": "s", "inside": True}}


class FreightContractTests(unittest.TestCase):
    def test_build_executes_actor_sign_cargo_and_motion_calls(self):
        for variant in module.VARIANTS:
            with self.subTest(variant=variant):
                adapter = Adapter()
                dossier = {"source_sha256": "d", "enterprise_use_reviewed": True,
                           "vehicle_id": "truck-1", "qualifies_commercial": module.VARIANTS[variant]["commercial"]}
                result = module.prepare_scene(adapter, site(), variant, dossier)
                names = [call[0] for call in adapter.calls]
                self.assertEqual(names[:7], ["assert_native_map", "assert_one_way_lane", "assert_yellow_curb", "set_civil_clock_window", "spawn_or_verify_sign", "spawn_vehicle", "drive_to_station"])
                self.assertIn("stop_and_hold", names)
                self.assertEqual("transfer_freight" in names, module.VARIANTS[variant]["activity"] != "none")
                self.assertEqual(result["target_station_m"] == 30, module.VARIANTS[variant]["in_zone"])

    def test_build_rejects_unsourced_site_and_status(self):
        source = site()
        del source["sign_observation_sha256"]
        with self.assertRaisesRegex(module.SourceError, "sign_observation_sha256"):
            module.prepare_scene(Adapter(), source, "freight_loading", {"source_sha256": "d"})
        with self.assertRaisesRegex(module.SourceError, "dossier/variant"):
            module.prepare_scene(Adapter(), site(), "noncommercial_loading", {"source_sha256": "d", "enterprise_use_reviewed": True, "vehicle_id": "truck-1", "qualifies_commercial": True})

    def test_saved_original_positive_and_missing_source_negative(self):
        result = module.audit_saved_original(packet(), case_id="case", variant="freight_loading")
        self.assertEqual(result["frames_checked"], 900)
        self.assertTrue(result["stopped_inside_zone"])
        p = packet()
        del p["freight_activity_source_sha256"]
        with self.assertRaisesRegex(module.SourceError, "freight_activity_source_sha256"):
            module.audit_saved_original(p, case_id="case", variant="freight_loading")

    def test_saved_original_rejects_frame_cargo_sign_and_zone_mismatch(self):
        for change, rejection in (
            (lambda p: p["frames"][400].update(original_frame=401), "noncontiguous"),
            (lambda p: p["freight_activity"].update(cargo_actor_id=None), "freight transfer"),
            (lambda p: p.update(sign_text_readback="Different"), "sign text mismatch"),
            (lambda p: p["frames"][500].update(ego_station_m=50, ego_body_station_min_m=48, ego_body_station_max_m=52), "stop spans zone"),
            (lambda p: p["frames"][500].update(ego_body_station_max_m=42), "stop spans zone"),
            (lambda p: p["frames"][500].update(time_s=26.0), "original 20 Hz timeline gap"),
            (lambda p: p["posted_window_check"].update(derived_from_sign_sha256="wrong"), "posted window source"),
        ):
            p = packet()
            change(p)
            with self.subTest(rejection=rejection), self.assertRaisesRegex(module.SourceError, rejection):
                module.audit_saved_original(p, case_id="case", variant="freight_loading")

    def test_comparison_rejects_changed_sign_and_non_deliberate_activity(self):
        left, right = packet(), packet()
        right["case_id"] = "other"
        self.assertEqual(module.audit_comparison(left, right, "posted_window")["deliberate_difference"], "posted_window")
        right["sign_observation_sha256"] = "another-sign"
        with self.assertRaisesRegex(module.SourceError, "sign_observation_sha256"):
            module.audit_comparison(left, right, "posted_window")
        right = packet()
        right["freight_activity"]["observed_action"] = "unloading"
        with self.assertRaisesRegex(module.SourceError, "freight_activity"):
            module.audit_comparison(left, right, "posted_window")

    def test_original_source_bundle_seals_files_and_joins_subject(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            p = packet()
            sources = {
                "frame_map": {"case_id": "case", "frames": list(range(900))},
                "native_map": {"map_name": "reviewed-map", **p["native_map_readback"]},
                "curb_observation": {"color": "yellow", **p["curb_observation"]},
                "sign_observation": {"verbatim_text": "Freight 8-18", **p["sign_observation"]},
                "commercial_dossier": dict(p["commercial_dossier"]),
                "freight_activity": dict(p["freight_activity"]),
            }
            entries = {}
            for name, value in sources.items():
                path = base / (name + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                entries[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            p["map_name"] = "reviewed-map"
            for name, field in module.SOURCE_FIELDS.items():
                if name != "native_result":
                    p[field] = entries[name]["sha256"]
            p["posted_window_check"]["derived_from_sign_sha256"] = entries["sign_observation"]["sha256"]
            path = base / "native_result.json"
            path.write_text(json.dumps(p), encoding="utf-8")
            entries["native_result"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(module.audit_source_bundle({"sources": entries}, case_id="case", variant="freight_loading")["frames_checked"], 900)
            sources["sign_observation"]["verbatim_text"] = "Changed text"
            (base / "sign_observation.json").write_text(json.dumps(sources["sign_observation"]), encoding="utf-8")
            with self.assertRaisesRegex(module.SourceError, "stale original source"):
                module.audit_source_bundle({"sources": entries}, case_id="case", variant="freight_loading")

    def test_physical_completion_uses_measured_values(self):
        measured = module.audit_saved_original(packet(), case_id="case", variant="freight_loading")
        self.assertTrue(module.require_case_completion(measured)["physical_completion"])
        measured["inside_posted_window"] = False
        with self.assertRaisesRegex(module.SourceError, "posted-time relation"):
            module.require_case_completion(measured)


if __name__ == "__main__":
    unittest.main()
