import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("saved_comparison", ROOT / "saved_comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
from freight_contract import SOURCE_FIELDS, SourceError
from test_freight_contract import packet


def seal(base, name, value):
    path = base / f"{name}.json"
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(base, variant):
    base.mkdir(exist_ok=True)
    original = packet(variant)
    original["case_id"] = f"{comparison.ASSIGNMENT}__{variant}"
    if variant == "freight_unloading":
        original["freight_activity"]["observed_action"] = "unloading"
    elif variant == "no_freight_activity":
        original["freight_activity"] = {"vehicle_id": "truck-1", "observed_action": "none",
                                        "cargo_actor_id": None, "observed_transfer_frames": []}
    elif variant == "noncommercial_loading":
        original["vehicle_id"] = "car-2"
        original["commercial_dossier"] = {"vehicle_id": "car-2", "enterprise_use_reviewed": True, "qualifies_commercial": False}
        original["freight_activity"]["vehicle_id"] = "car-2"
    elif variant == "outside_posted_time":
        original["posted_window_check"]["inside"] = False
    elif variant == "outside_yellow_zone":
        for frame in original["frames"]:
            frame["ego_station_m"] = 60
            frame["ego_body_station_min_m"] = 58
            frame["ego_body_station_max_m"] = 62

    context = {
        "case_id": original["case_id"], "native_map_sha256": "map-sha", "native_road_id": 2,
        "native_lane_id": -1, "curb_observation_sha256": "curb-sha",
        "sign_observation_sha256": "sign-sha", "zone": original["zone"],
        "posted_conditions": original["posted_conditions"], "camera_plan_sha256": "camera-sha",
        "capture_rate_hz": 20, "capture_frames": 900, "ego_controller_sha256": "ctrl-sha",
        "freight_prop_blueprint": "prop.cargo", "vehicle_id": original["vehicle_id"],
        "commercial_dossier_sha256": "dossier-base" if variant != "noncommercial_loading" else "dossier-other",
        "civil_time_source_sha256": "civil-base" if variant != "outside_posted_time" else "civil-other",
    }
    sources = {
        "frame_map": {"case_id": original["case_id"], "frames": list(range(900))},
        "native_map": {"map_name": "ReviewedTown", **original["native_map_readback"]},
        "curb_observation": {"color": "yellow", **original["curb_observation"]},
        "sign_observation": {"verbatim_text": "Freight 8-18", **original["sign_observation"]},
        "commercial_dossier": dict(original["commercial_dossier"]),
        "freight_activity": dict(original["freight_activity"]),
    }
    refs = {name: seal(base, name, value) for name, value in sources.items()}
    refs["comparison_context"] = seal(base, "comparison_context", context)
    original["map_name"] = "ReviewedTown"
    original["comparison_context_sha256"] = refs["comparison_context"]["sha256"]
    for name, field in SOURCE_FIELDS.items():
        if name != "native_result":
            original[field] = refs[name]["sha256"]
    original["posted_window_check"]["derived_from_sign_sha256"] = refs["sign_observation"]["sha256"]
    refs["native_result"] = seal(base, "native_result", original)
    return {"case_id": original["case_id"], "kind": "delivery", "acquisition_kind": "original_native", "sources": refs}


class SavedComparisonTests(unittest.TestCase):
    def test_all_five_exact_pairs_have_source_bound_positive_proof(self):
        for comparison_id, (_, variant, _) in comparison.PAIRS.items():
            with self.subTest(comparison_id=comparison_id), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                left = fixture(base / "left", "freight_loading")
                right = fixture(base / "right", variant)
                result = comparison.audit_pair(left, right, comparison_id)
                self.assertTrue(result["source_integrity"])
                self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_rejects_wrong_case_diagnostic_and_stale_source(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            left = fixture(base / "left", "freight_loading")
            right = fixture(base / "right", "freight_unloading")
            bad = copy.deepcopy(right)
            bad["case_id"] = "foreign"
            with self.assertRaisesRegex(SourceError, "exact case"):
                comparison.audit_pair(left, bad, "activity_direction")
            bad = copy.deepcopy(right)
            bad["acquisition_kind"] = "diagnostic"
            with self.assertRaisesRegex(SourceError, "diagnostic"):
                comparison.audit_pair(left, bad, "activity_direction")
            context_path = Path(right["sources"]["comparison_context"]["path"])
            context_path.write_text(context_path.read_text() + " ", encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "stale original source"):
                comparison.audit_pair(left, right, "activity_direction")

    def test_rejects_unchanged_dimension_and_uncontrolled_camera(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            left = fixture(base / "left", "freight_loading")
            right = fixture(base / "right", "freight_unloading")
            native_ref = right["sources"]["native_result"]
            native = json.loads(Path(native_ref["path"]).read_text())
            native["freight_activity"]["observed_action"] = "loading"
            right["sources"]["native_result"] = seal(base / "right", "native_result", native)
            with self.assertRaisesRegex(SourceError, "original freight_activity field mismatch"):
                comparison.audit_pair(left, right, "activity_direction")

            right = fixture(base / "right", "freight_unloading")
            context_ref = right["sources"]["comparison_context"]
            context = json.loads(Path(context_ref["path"]).read_text())
            context["camera_plan_sha256"] = "other-camera"
            right["sources"]["comparison_context"] = seal(base / "right", "comparison_context", context)
            native_ref = right["sources"]["native_result"]
            native = json.loads(Path(native_ref["path"]).read_text())
            native["comparison_context_sha256"] = right["sources"]["comparison_context"]["sha256"]
            right["sources"]["native_result"] = seal(base / "right", "native_result", native)
            with self.assertRaisesRegex(SourceError, "camera_plan_sha256"):
                comparison.audit_pair(left, right, "activity_direction")


if __name__ == "__main__":
    unittest.main()
