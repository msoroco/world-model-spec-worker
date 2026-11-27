"""Regenerate nine exact inline Native bundles from reviewed local source code."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PLAN = json.loads((ROOT / "case-plan.json").read_text())
CAMERAS = [
    {"name": name, "width": width, "height": height, "fov_deg": 75,
     "pose_strategy": "source-hashed original rider, right-arm, road and right-turn views"}
    for name, width, height in (("overview", 1920, 1080),
                                ("approach", 1280, 720),
                                ("reference_corner", 1280, 720),
                                ("driver_reference", 1280, 720))]
CHANNELS = [
    {"name": name, "unit": unit, "method": method,
     "sampling_rate_hz": 20, "time_window": "all 900 original frames",
     "reference_frame": "reviewed original roadway and rider heading",
     "uncertainty": "original pixels and legal form pending"}
    for name, unit, method in (
        ("roadway_occupancy", "boolean", "source polygon and original contact point"),
        ("right_arm_pose", "m", "original shoulder/elbow/wrist right, forward and vertical projections"),
        ("right_turn_heading", "unit vector", "original cycle heading and reviewed route"),
        ("camera_frame_identity", "original frame", "four original camera frame identity join"))]
DESCRIPTION = {
    "channels": CHANNELS,
    "context_inputs": [{"name": "reviewed_signal_scene", "unit": "source",
                        "method": "source-hashed OpenDRIVE, highway, roadway, shoulder, covered operator, rider rig and route"}],
    "limitations": ["NRS 484B.420 form details absent in frozen law record.",
                    "Actual arm articulation and camera-visible posture require original review."]}
TEST = '''import json\nimport unittest\nfrom pathlib import Path\nfrom signal_scene import case_parts, requested_pose\n\nclass ExactOffline(unittest.TestCase):\n    def test_selected_case_and_pose(self):\n        root=Path(__file__).resolve().parents[1]\n        config=json.loads((root/"config.json").read_text())\n        kind,posture=case_parts(config["selected_case_id"])\n        self.assertEqual(kind,config["case"]["operator_vehicle_kind"])\n        self.assertEqual(posture,config["case"]["posture_key"])\n        self.assertIn("wrist",requested_pose(posture))\n\nif __name__=="__main__":unittest.main()\n'''


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    ids = [case["case_id"] for case in PLAN["cases"]]
    (ROOT / "tests").mkdir(exist_ok=True)
    (ROOT / "tests/test_offline.py").write_text(TEST, encoding="utf-8")
    source_names = ("runner.py", "signal_scene.py", "signal_measurements.py",
                    "analysis.py", "native_adapter.py")
    source_files = [{"path": name, "source": str((ROOT / name).relative_to(ROOT.parents[1])),
                     "content": (ROOT / name).read_text(encoding="utf-8")}
                    for name in source_names]
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "status": "partial", "cases": [],
                "runtime_manifest_sha256": sha(ROOT.parents[1] / "runtime/SOURCE-MANIFEST.json")}
    for index, case in enumerate(PLAN["cases"]):
        case_id = case["case_id"]
        suffix = case_id[len(ASSIGNMENT) + 2:]
        kind = case["operator_vehicle_kind"]
        posture = suffix[len(kind) + 1:]
        config = {
            "assignment_id": ASSIGNMENT, "law_id": "NRS-484B-769", "cell_id": "C229813",
            "actor": "cycle_or_scooter_operator", "selected_case_id": case_id,
            "supported_case_ids": ids, "rate_hz": 20, "duration_s": 45,
            "frame_count": 900, "required_atoms": [], "source_packets": [],
            "controller": {"target_speed_mps": 4.0, "max_throttle": 0.5,
                           "steer_gain": 0.015},
            "source_gate": "reviewed original rider arm scene and source bytes required",
            "cameras": CAMERAS,
            "physical_completion": {"criterion": "travel_progress",
                                    "motion_source": "trace.jsonl",
                                    "position_key": "position_m",
                                    "minimum_progress_m": 5.0,
                                    "minimum_samples": 3,
                                    "engineering_tolerances_not_legal": True,
                                    "completion_goal_method": "5m original rider travel as an engineering motion proxy; original signal and turn require independent review"},
            "case": {"case_id": case_id, "operator_vehicle_kind": kind,
                     "posture_key": posture,
                     "requested_signal_posture": case["requested_signal_posture"],
                     "recording_description": DESCRIPTION}}
        folder = ROOT if index == 0 else ROOT / "cases" / suffix
        write_json(folder / "config.json", config)
        files = source_files + [
            {"path": "config.json", "source": str((folder / "config.json").relative_to(ROOT.parents[1])),
             "content": (folder / "config.json").read_text(encoding="utf-8")},
            {"path": "tests/test_offline.py", "content": TEST}]
        construction = {
            "law_id": "NRS-484B-769", "cell_id": "C229813",
            "actor": "cycle_or_scooter_operator", "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_fixture": False, "files": files,
            "measurement_plan": {"procedure": "analysis.py",
                                 "source": "reviewed original roadway, route and right-arm joints at 20 Hz"},
            "recording_description": DESCRIPTION,
            "static_checks": ["exact covered kind", "source hashes", "live OpenDRIVE hash",
                              "clockwise route", "roadway outside shoulder", "independently actuated rider rig"],
            "termination_rules": {"duration_s": 45,
                                  "missing_original_source": "reject before accepted attempt"},
            "mechanisms": ["reviewed covered cycle and rider blueprint spawn",
                           "source-gated right-turn route", "right-arm pose actuation with original joint readback",
                           "four synchronized original cameras"]}
        write_json(folder / "construction.json", construction)
        fallback_folder = ROOT / "fallbacks" / suffix
        fallback_config = dict(config)
        fallback_config["controller"] = {"target_speed_mps": 3.0,
                                         "max_throttle": 0.4, "steer_gain": 0.015}
        write_json(fallback_folder / "config.json", fallback_config)
        fallback_files = [dict(item) for item in files]
        fallback_files = [({"path": "config.json",
                           "source": str((fallback_folder / "config.json").relative_to(ROOT.parents[1])),
                           "content": (fallback_folder / "config.json").read_text(encoding="utf-8")}
                          if item["path"] == "config.json" else item) for item in fallback_files]
        fallback = dict(construction)
        fallback["files"] = fallback_files
        fallback["mechanisms"] = list(construction["mechanisms"]) + [
            "predeclared slower target speed for measured route tracking failure"]
        write_json(fallback_folder / "construction.json", fallback)
        manifest["cases"].append({
            "case_id": case_id, "kind": "delivery",
            "construction": str((folder / "construction.json").relative_to(ROOT)),
            "construction_sha256": sha(folder / "construction.json"),
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "source_gate": "reviewed original roadway, covered rider and articulated right arm",
            "candidate_risk": {"status": "physical", "reason": case["physical_risk"]["reason"]},
            "candidates": [{"id": "fallback1",
                "construction": str((fallback_folder / "construction.json").relative_to(ROOT)),
                "construction_sha256": sha(fallback_folder / "construction.json"),
                "changed_knobs": ["controller target speed 4.0 to 3.0 m/s",
                                  "maximum throttle 0.5 to 0.4"],
                "trigger": {"source": "sealed original cycle route trace",
                            "metric": "maximum original cross-track distance from reviewed route in metres",
                            "failure_condition": "primary has source-complete original trace with route deviation above 2.0 m"}}], "acquisition": {
                channel["name"]: {"entrypoint": "analysis.py", "method": channel["method"],
                                  "evidence": "signal-readback.jsonl"}
                for channel in CHANNELS},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}})
    write_json(ROOT / "execution-manifest.draft.json", manifest)
    PLAN["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name, "subject": "operator face, right hand/arm, cycle, roadway and right turn",
                      "interval": "all 900 original frames"} for name in
                     ("overview", "approach", "reference_corner", "driver_reference")]}
    PLAN["source_observation_mapping"] = {}
    observation_channels = {
        "operator_class_and_identity": "roadway_occupancy",
        "highway_roadway_and_shoulder": "roadway_occupancy",
        "right_turn_route": "right_turn_heading",
        "right_hand_arm_posture": "right_arm_pose",
    }
    for observation in PLAN["observations"]:
        name = observation["name"]
        if name == "actual_video_visibility":
            observation["mandatory"] = False
            observation["method"] = "independent source-bound full-video pixel audit after original capture"
        elif name in observation_channels:
            observation["name"] = observation_channels[name]
            observation["mandatory"] = True
    PLAN["requirement_dispositions"] = [{
        "requirement": "NRS-484B-769", "source": "inputs/testing__C229813__NRS-484B-769__cycle_or_scooter_operator/assignment.json",
        "status": "selected_required", "case_ids": ids,
        "evidence_or_gap": "No accepted original signal recording.",
        "reason": "Three covered kinds and three pose probes each; NRS 484B.420 reference details remain unresolved."}]
    write_json(ROOT / "case-plan.json", PLAN)
    print(json.dumps({"bundles": len(ids), "first": ids[0]}, sort_keys=True))


if __name__ == "__main__":
    build()
