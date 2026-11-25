import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path.cwd() / ".runtime-work"
SCRATCH.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("saved_comparison", ROOT / "saved_comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
from freight_contract import SOURCE_FIELDS, SourceError
from saved_delivery import CAMERAS
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
        original["civil_time"]["local_datetime"] = "2026-11-23T20:00:00"
    elif variant == "outside_yellow_zone":
        for frame in original["frames"]:
            station = 5 + 55 * min(frame["original_frame"], 200) / 200
            frame["ego_station_m"] = station
            frame["ego_body_station_min_m"] = station - 2
            frame["ego_body_station_max_m"] = station + 2
            frame["ego_speed_mps"] = 5.5 if frame["original_frame"] < 200 else 0.0
    for frame in original["frames"]:
        frame["native_frame"] = frame["original_frame"] + 101

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
        "sign_observation": {"verbatim_text": "Freight 8-18",
                             "civil_windows": original["posted_conditions"]["civil_windows"],
                             "freight_permitted": True, **original["sign_observation"]},
        "commercial_dossier": dict(original["commercial_dossier"]),
        "freight_activity": dict(original["freight_activity"]),
        "civil_time": {"timezone": original["civil_time"]["timezone"],
                       "local_datetime": original["civil_time"]["local_datetime"]},
    }
    refs = {name: seal(base, name, value) for name, value in sources.items()}
    context["civil_time_source_sha256"] = refs["civil_time"]["sha256"]
    refs["comparison_context"] = seal(base, "comparison_context", context)
    original["map_name"] = "ReviewedTown"
    original["comparison_context_sha256"] = refs["comparison_context"]["sha256"]
    for name, field in SOURCE_FIELDS.items():
        if name != "native_result":
            original[field] = refs[name]["sha256"]
    original["civil_time"]["source_sha256"] = refs["civil_time"]["sha256"]
    original["posted_window_check"]["derived_from_sign_sha256"] = refs["sign_observation"]["sha256"]
    refs["native_result"] = seal(base, "native_result", original)
    map_path = base / "frame-map.jsonl"
    motion_path = base / "freight_motion.jsonl"
    map_path.write_text("".join(json.dumps({"video_frame": row["original_frame"],
                                            "native_frame": row["native_frame"],
                                            "time_s": row["time_s"]}) + "\n" for row in original["frames"]))
    motion_path.write_text("".join(json.dumps(row) + "\n" for row in original["frames"]))
    raw = {"frame_map": {"path": str(map_path), "sha256": hashlib.sha256(map_path.read_bytes()).hexdigest()},
           "motion": {"path": str(motion_path), "sha256": hashlib.sha256(motion_path.read_bytes()).hexdigest()}}
    media = {}
    for name in CAMERAS:
        path = base / (name + ".mkv")
        path.write_bytes((name + " source-shaped fixture").encode())
        media[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"case_id": original["case_id"], "kind": "delivery",
            "acquisition_kind": "original_native", "sources": refs, "raw_sources": raw,
            "job_id": "fixture-job", "attempt_id": "fixture-attempt",
            "recording_id": "fixture-recording", "native_result_sha256": refs["native_result"]["sha256"],
            "media": media}


def fake_probe(path):
    width, height = CAMERAS[path.stem]
    return {"width": width, "height": height, "r_frame_rate": "20/1",
            "nb_read_frames": "900"}


class SavedComparisonTests(unittest.TestCase):
    def test_all_five_exact_pairs_have_source_bound_positive_proof(self):
        for comparison_id, (_, variant, _) in comparison.PAIRS.items():
            with self.subTest(comparison_id=comparison_id), tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
                base = Path(temp)
                left = fixture(base / "left", "freight_loading")
                right = fixture(base / "right", variant)
                result = comparison.audit_pair(left, right, comparison_id)
                self.assertTrue(result["source_integrity"])
                self.assertEqual(result["legal_conclusion"], "unresolved")

    def test_rejects_wrong_case_diagnostic_and_stale_source(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
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
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
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

    def test_rejects_hash_valid_comparison_context_outside_attempt(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            base = Path(temp)
            left_root = base / "left"
            right_root = base / "right"
            left = fixture(left_root, "freight_loading")
            right = fixture(right_root, "freight_unloading")
            source = Path(right["sources"]["comparison_context"]["path"])
            foreign = base / "foreign-context.json"
            foreign.write_bytes(source.read_bytes())
            right["sources"]["comparison_context"]["path"] = str(foreign)
            with self.assertRaisesRegex(SourceError, "comparison source escapes original attempt"):
                comparison.audit_pair(left, right, "activity_direction",
                                      attempt_roots=(left_root, right_root),
                                      media_probe=fake_probe)

    def test_production_pair_checks_both_original_media_sources(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            base = Path(temp)
            left_root, right_root = base / "left", base / "right"
            left = fixture(left_root, "freight_loading")
            right = fixture(right_root, "freight_unloading")
            result = comparison.audit_pair(left, right, "activity_direction",
                                           attempt_roots=(left_root, right_root),
                                           media_probe=fake_probe)
            self.assertEqual(result["deliberate_measurement"], "observed_action")
            (right_root / "overview.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(SourceError, "stale media source"):
                comparison.audit_pair(left, right, "activity_direction",
                                      attempt_roots=(left_root, right_root),
                                      media_probe=fake_probe)


if __name__ == "__main__":
    unittest.main()
