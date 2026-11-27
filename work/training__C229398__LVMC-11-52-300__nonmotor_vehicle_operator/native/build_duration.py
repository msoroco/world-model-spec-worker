"""Materialize exact below/at/above Native request bundles for CPU offline checks."""

import hashlib
import json
from pathlib import Path

from duration_policy import RATE_HZ, TARGETS, TOTAL_FRAMES, comparison_invariants, stop_frame


ROOT = Path(__file__).resolve().parent
ASSIGNMENT_DIR = ROOT.parent
ASSIGNMENT = ASSIGNMENT_DIR.name
LAW = "LVMC-11-52-300"


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    road = (ROOT / "parking-road.xodr").read_text()
    runner = (ROOT / "duration_runner.py").read_text()
    duration = (ROOT / "duration_policy.py").read_text()
    gate = (ROOT / "source_gate.py").read_text()
    measurement = (ROOT / "selected_measurement.py").read_text()
    finalizer = (ROOT / "finalize.py").read_text()
    cameras = [
        {"name": "overview", "width": 1920, "height": 1080,
         "fov_deg": 85, "location_xyz_m": [35, -8, 18], "pitch_deg": -55,
         "pose_strategy": "same fixed whole curb and approach"},
        {"name": "approach", "width": 1280, "height": 720,
         "fov_deg": 90, "location_xyz_m": [30, -3, 2.5], "pitch_deg": -5,
         "pose_strategy": "same near curb approach"},
        {"name": "reference_corner", "width": 1280, "height": 720,
         "fov_deg": 75, "location_xyz_m": [40, -6, 3], "pitch_deg": -25,
         "pose_strategy": "same curb reference"},
        {"name": "driver_reference", "width": 1280, "height": 720,
         "fov_deg": 90, "location_xyz_m": [42, -3, 2.5], "pitch_deg": -10,
         "pose_strategy": "same subject and operator view"},
    ]
    common = {
        "format": "c229398-night-parking-duration-request-v2",
        "status": "selected_cpu_draft", "assignment_id": ASSIGNMENT,
        "law_id": LAW, "cell_id": "C229398", "actor": "nonmotor_vehicle_operator",
        "prototype_blueprint": "vehicle.diamondback.century",
        "device_classification": "unresolved", "road_sha256": hashlib.sha256(road.encode()).hexdigest(),
        "rate_hz": RATE_HZ, "capture_frames": TOTAL_FRAMES,
        "duration_s": TOTAL_FRAMES / RATE_HZ, "cameras": cameras,
        "weather": "sun altitude -20 degrees, clear precipitation and fog",
        "parking_target_xy_m": [40.0, -3.0],
        "source_context_policy": "original hash-bound nonmotor and street review before Native",
        "required_atoms": [], "source_packets": [],
        "supported_case_ids": [ASSIGNMENT + "__" + suffix for suffix in TARGETS],
        "original_native_observed": False, "physical_or_legal_acceptance": False,
    }
    configs = {}
    for suffix, target in TARGETS.items():
        case_id = ASSIGNMENT + "__" + suffix
        config = dict(common, case_id=case_id, selected_case_id=case_id,
                      case={"case_id": case_id},
                      parking_stop_frame=stop_frame(case_id),
                      requested_stationary_duration_s=target)
        configs[suffix] = config
    comparison_invariants(configs)
    receipts = {}
    for suffix, config in configs.items():
        case_id = config["case_id"]
        target_dir = ASSIGNMENT_DIR if suffix == "below_30" else ASSIGNMENT_DIR / "cases" / suffix
        target_dir.mkdir(parents=True, exist_ok=True)
        tests = ("import json\nimport sys\nimport unittest\nfrom pathlib import Path\n"
                 "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
                 "from runner import check, request\n\n"
                 "class TestDuration(unittest.TestCase):\n"
                 "    def test_exact_request(self):\n"
                 "        cfg = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())\n"
                 "        self.assertTrue(check()['passed'])\n"
                 "        self.assertEqual(request(cfg['parking_stop_frame'] - 1, cfg)['phase'], 'approach')\n"
                 "        self.assertEqual(request(cfg['parking_stop_frame'], cfg)['phase'], 'parking_request')\n"
                 "        self.assertEqual(request(cfg['capture_frames'] - 1, cfg)['requested_stationary_duration_s'], cfg['requested_stationary_duration_s'])\n")
        recording = {
            "channels": [
                {"name": name, "unit": "structured", "sampling_rate_hz": RATE_HZ,
                 "method": "original Native pose/velocity plus reviewed source context",
                 "time_window": "all 36063 original frames", "reference_frame": "Native world and civil clock",
                 "uncertainty": "50 ms frame spacing; legal activity and device class need independent review"}
                for name in ("drv.standing_or_parked", "ru.motor_vehicle", "ru.trailer_or_combination",
                             "kin.time", "env.civil_time", "drv.condition_in_effect", "st.roadway")],
            "context_inputs": [{"name": "qualifying_source_review", "unit": "structured",
                                "method": "original hash-bound source packet"}],
            "duration_s": TOTAL_FRAMES / RATE_HZ, "rate_hz": RATE_HZ,
            "camera_views": [camera["name"] for camera in cameras],
            "limitations": ["Bicycle blueprint alone does not certify a qualifying legal vehicle",
                            "No Native execution or real source media captured"]}
        config["recording_description"] = recording
        config["case"]["recording_description"] = recording
        config_text = encoded(config)
        files = [("runner.py", runner), ("duration_policy.py", duration),
                 ("source_gate.py", gate), ("selected_measurement.py", measurement),
                 ("finalize.py", finalizer), ("parking-road.xodr", road),
                 ("config.json", config_text), ("tests/test_duration.py", tests)]
        for relative, content in files:
            path = target_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        construction = {
            "case_id": case_id, "law_id": LAW, "cell_id": "C229398",
            "actor": "nonmotor_vehicle_operator", "entrypoint": "runner.py",
            "files": [{"path": relative, "content": content} for relative, content in files],
            "measurement_plan": {"entrypoint": "finalize.py", "required_sources": [
                "native-actor-frames.jsonl", "review-source.json",
                "street-geometry.json", "video_frames.jsonl"],
                "source_review_required": True},
            "recording_description": recording,
            "static_checks": ["exact 20 Hz duration bracket", "identical road and four cameras",
                              "original source review required before Native"],
            "mechanisms": ["config-driven parking stop frame", "bicycle prototype motion request",
                           "original pose and camera frame join"],
            "termination_rules": ["36063 synchronized frames", "restore Native world"],
            "status": "selected_cpu_draft_original_capture_pending",
        }
        construction_path = target_dir / "construction.json"
        construction_path.write_text(encoded(construction))
        receipts[suffix] = {"case_id": case_id,
                            "construction": str(construction_path.relative_to(ASSIGNMENT_DIR)),
                            "construction_sha256": digest(construction_path),
                            "kind": "draft_not_ready", "candidates": []}
    manifest = {"format": "worker-duration-construction-draft-v1",
                "assignment_id": ASSIGNMENT, "status": "partial_cpu_construction",
                "cases": list(receipts.values())}
    manifest_path = ASSIGNMENT_DIR / "duration-construction-draft.json"
    manifest_path.write_text(encoded(manifest))
    print(encoded({"manifest": str(manifest_path), "sha256": digest(manifest_path),
                   "cases": receipts}), end="")


if __name__ == "__main__":
    build()
