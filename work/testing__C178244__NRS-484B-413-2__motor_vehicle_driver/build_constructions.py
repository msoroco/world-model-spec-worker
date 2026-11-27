"""Materialize ten exact, inline, source-gated signal constructions."""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
PROPOSALS = json.loads((ROOT / "proposals/cases.json").read_text())
DESCRIPTION = {item["case_id"]: item["recording_description"]
               for item in PROPOSALS["cases"] if item["target_law_id"]}
SOURCES = ("runner.py", "analysis.py", "saved_export.py", "native_capture.py", "native_capture_contract.py",
           "native_site.py", "carla_adapter.py", "signal_controller.py",
           "signal_measure.py", "signal_audit.py", "source_audit.py",
           "turn_signal_probe.py", "test_native_capture.py", "test_signal_construction.py",
           "test_signal_measure.py", "test_turn_signal_probe.py", "case-plan.json")
TESTS = ("tests/test_current.py",)

CAMERAS = [
    {"name": "overview", "width": 1920, "height": 1080,
     "pose_strategy": "reviewed fixed highway and district overview", "fov_deg": 90},
    {"name": "approach", "width": 1280, "height": 720,
     "pose_strategy": "reviewed fixed full signal approach and left-turn path", "fov_deg": 90},
    {"name": "reference_corner", "width": 1280, "height": 720,
     "pose_strategy": "reviewed fixed district frontage and turn corner", "fov_deg": 90},
    {"name": "driver_reference", "width": 1280, "height": 720,
     "pose_strategy": "reviewed ego mounted forward and left reference", "fov_deg": 90},
]


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    all_ids = [item["case_id"] for item in PLAN["cases"]]
    manifest_cases = []
    for index, item in enumerate(PLAN["cases"]):
        case_id = item["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        folder = ROOT if index == 0 else ROOT / "cases" / tag
        config = {"assignment_id": PLAN["assignment_id"],
                  "selected_case_id": case_id, "supported_case_ids": all_ids,
                  "law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
                  "actor": PLAN["actor"], "rate_hz": 20, "duration_s": 45,
                  "required_atoms": [], "source_packets": [], "cameras": CAMERAS,
                  "controller_lead_samples": 1,
                  "case": {"case_id": case_id, "target": item["target"],
                           "recording_description": DESCRIPTION[case_id]},
                  "course": "left_turn",
                  "physical_completion": {"criterion": "turn",
                                          "motion_source": "body_history.jsonl",
                                          "body_key": "body_vertices_m",
                                          "heading_key": "heading_deg",
                                          "turn_degrees": 90,
                                          "turn_sign": 1,
                                          "destination_road": None,
                                          "turn_tolerance_deg": 30,
                                          "minimum_progress_m": 10,
                                          "minimum_samples": 2,
                                          "engineering_tolerances_not_legal": True}}
        config_path = folder / "config.json"
        dump(config_path, config)
        files = []
        for name in (*SOURCES, *TESTS, "config.json"):
            source = config_path if name == "config.json" else ROOT / name
            files.append({"path": name, "source": source.relative_to(REPO).as_posix(),
                          "content": source.read_text()})
        construction = {"law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
                        "actor": PLAN["actor"], "case_id": case_id,
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": DESCRIPTION[case_id],
                        "mechanisms": ["SHA-verified original district and left-turn site before CARLA import",
                                       "20 Hz sampled left-signal actuator and original readback",
                                       "four synchronized original CARLA camera streams"],
                        "measurement_plan": {"signal_distance": "Saved sampled path length of the last uninterrupted left-signal interval before observed course change; exact 100 ft business/residential or 300 ft other-area statutory reference.",
                                             "numeric_triple": "Reject each below/at/above probe when original measured distances do not separate."},
                        "static_checks": ["exact case and source hash", "reviewed left-turn route and case-specific district context",
                                          "900 original frame and four camera joins"],
                        "termination_rules": ["stop at 900 ticks", "abort on source or camera mismatch"]}
        construction_path = folder / "construction.json"
        dump(construction_path, construction)
        fallback_config = copy.deepcopy(config)
        fallback_config["controller_lead_samples"] = 2
        fallback_folder = ROOT / "cases" / tag / "fallback1"
        fallback_config_path = fallback_folder / "config.json"
        dump(fallback_config_path, fallback_config)
        fallback = copy.deepcopy(construction)
        for entry in fallback["files"]:
            if entry["path"] == "config.json":
                entry["source"] = fallback_config_path.relative_to(REPO).as_posix()
                entry["content"] = fallback_config_path.read_text()
        fallback["mechanisms"].append("two-sample engineering lead for measured onset drift")
        fallback_path = fallback_folder / "construction.json"
        dump(fallback_path, fallback)
        contract_rows = []
        for position, disposition in enumerate(PLAN["requirement_dispositions"]):
            if case_id not in disposition["case_ids"]:
                continue
            requirement = disposition["requirement"]
            if requirement.startswith("Source-reviewed"):
                key, kind, inputs = "site_context_measurement", "sourced_context", ["original-site.json"]
            elif "regardless of weather" in requirement:
                key, kind, inputs = "weather_independence_measurement", "measured", ["original-turn-signal.json"]
            else:
                key, kind, inputs = "signal_distance_measurement", "measured", ["original-turn-signal.json", "video_frames.jsonl"]
            contract_rows.append({"disposition_index": position,
                                  "requirement": requirement,
                                  "source": disposition["source"],
                                  "output_key": key, "method": "build_report",
                                  "value_type": "object", "kind": kind,
                                  "inputs": inputs})
        contract_path = folder / "measurement-contract.json"
        dump(contract_path, {"format": "worker-measurement-contract",
                             "requirements": contract_rows,
                             "negative": {"remove": ["original-turn-signal.json"],
                                          "error_contains": "Missing required source: original-turn-signal.json"}})
        manifest_cases.append({"case_id": case_id, "kind": "delivery",
                               "construction": construction_path.relative_to(ROOT).as_posix(),
                               "construction_sha256": sha(construction_path),
                               "fixture_recipe": (ROOT / ("diagnostic-" + tag + "-recipe.json")).relative_to(REPO).as_posix(),
                               "measurement_contract": contract_path.relative_to(ROOT).as_posix(),
                               "measurement_procedure": {"entrypoint": "analysis.py"},
                               "acquisition": {name: {"entrypoint": "analysis.py",
                                  "evidence": "channels/" + name + ".jsonl",
                                  "method": "Saved projection of SHA-verified original Native samples"}
                                  for name in ("native_frame", "ego_xy", "left_signal",
                                               "course_change", "weather", "four_camera_frames")},
                               "native_handoff": {"host_env_var": "CARLA_HOST",
                                                  "port_env_var": "CARLA_PORT",
                                                  "python_env_var": "CARLA_PYTHON",
                                                  "site_env_var": "SIGNAL_SITE_PATH",
                                                  "site_sha256_env_var": "SIGNAL_SITE_SHA256"},
                               "candidate_risk": item["physical_risk"],
                               "candidates": [{"id": "fallback1",
                                               "construction": fallback_path.relative_to(ROOT).as_posix(),
                                               "construction_sha256": sha(fallback_path),
                                               "changed_knobs": ["left-signal controller lead: one to two sampled speed steps"],
                                               "trigger": {"source": "original Native turn signal samples and saved signal_measure.py result",
                                                           "metric": "sampled uninterrupted preturn signal distance and course-change onset",
                                                           "failure_condition": "primary signal onset drift leaves measured preturn distance below its selected target or course-change onset outside the reviewed route"}}]})
        for context_name in ("highway", "district_frontage_and_use",
                             "freight_loading_zone", "driver_and_vehicle"):
            manifest_cases[-1]["acquisition"][context_name] = {
                "entrypoint": "analysis.py", "evidence": "channels/context.json",
                "method": "Saved projection of SHA-verified original site inventory"}
    dump(ROOT / "execution-manifest.json",
         {"format": "worker-execution-manifest",
          "assignment_id": PLAN["assignment_id"],
          "runtime_manifest_sha256": json.loads((REPO / "batch.json").read_text())["runtime"]["source_manifest_sha256"],
          "cases": manifest_cases,
          "comparisons": PLAN["comparisons"]})


if __name__ == "__main__":
    main()
