"""Build six exact C111278 offline Native case bundles from local source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
SOURCES = (
    "runner.py", "native_case_runner.py", "native_sight_capture.py",
    "native_route_reader.py", "native_ray_reader.py", "native_speed_controller.py",
    "sight_construction.py", "sight_measurement.py", "saved_sight.py",
    "carla_camera_adapter.py", "comparison_audit.py", "delivery_audit.py",
    "analysis.py",
    "case-plan.json", "tests/test_bundle.py",
)
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    semantic = {case["case_id"] for case in proposal["cases"]
                if case["target_type"] != "baseline"}
    if len(plan["cases"]) != 6 or {case["case_id"] for case in plan["cases"]} != semantic:
        raise ValueError("six exact C111278 cases or semantic proposal differ")
    records = []
    for case in plan["cases"]:
        suffix = case["case_key"]
        case_id = AID + "__" + suffix
        if case["case_id"] != case_id:
            raise ValueError("case identity differs")
        config = {
            "assignment_id": AID, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "selected_case_id": case_id, "case_key": suffix,
            "requested_traversal_speed_mph": case["requested_traversal_speed_mph"],
            "requested_occluder": case["requested_occluder"],
            "through_designation": case["through_designation"],
            "traffic_controlled_intersection": case["traffic_controlled_intersection"],
            "plan_sha256": sha(ROOT / "case-plan.json"),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": [{"name": name, "width": width, "height": height,
                         "pose_strategy": "reviewed intersection source and intended visible subject",
                         "fov_deg": 90} for name, width, height in CAMERAS],
            "required_sources": ["reviewed_site_packet", "cited_intersection_boundary",
                                 "original_route_and_arm_rays", "original_camera_media"],
            "required_atoms": [], "source_packets": [], "diagnostic_only": True,
            "controller_gain": 1.0,
            "physical_completion": {"criterion": "travel_progress",
                                    "motion_source": "trace.jsonl",
                                    "minimum_progress_m": 30.48,
                                    "context_sources": ["site.json"]},
            "supported_case_ids": [item["case_id"] for item in plan["cases"]],
        }
        files = [{"path": name, "content": (ROOT / name).read_text(),
                  "source": str((ROOT / name).relative_to(REPO))} for name in SOURCES]
        files.append({"path": "config.json", "content": encoded(config)})
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": case["recording_description"],
            "measurement_plan": {"source": "native-sight.json", "method": "saved_sight.verify"},
            "static_checks": ["runner.py --check", "tests/test_bundle.py"],
            "termination_rules": ["900 original 20 Hz frames", "complete intersection traversal"],
            "mechanisms": ["reviewed route", "independent arm rays", "speed controller"],
            "files": files,
        }
        path = ROOT / ("construction-" + suffix + ".json")
        path.write_text(encoded(construction))
        fallback_config = dict(config, controller_gain=0.75)
        fallback_files = [dict(item) if item["path"] != "config.json"
                          else {"path": "config.json", "content": encoded(fallback_config)}
                          for item in files]
        fallback = dict(construction, files=fallback_files)
        fallback_path = ROOT / ("fallback-" + suffix + "-construction.json")
        fallback_path.write_text(encoded(fallback))
        records.append({"case_id": case_id, "kind": "delivery",
                        "construction": path.name, "construction_sha256": sha(path),
                        "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "candidate_risk": case["candidate_risk"],
                        "candidates": [{"id": "fallback1",
                                        "construction": fallback_path.name,
                                        "construction_sha256": sha(fallback_path),
                                        "changed_knobs": ["controller_gain: 1.0 to 0.75"],
                                        "trigger": {"source": "selected saved original traversal-speed observation",
                                                    "metric": "maximum traversal speed in m/s",
                                                    "failure_condition": "source-complete primary overshoots requested speed by more than 0.5 m/s"},
                                        "risk_note": "Only bounded engineering throttle response changes; law, site, requested speed, rays and camera plan remain fixed."}],
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT",
                                           "site_root_env_var": "C111278_SITE_ROOT"}})
        if suffix == plan["cases"][0]["case_key"]:
            (ROOT / "config.json").write_text(encoded(config))
            (ROOT / "construction.json").write_text(encoded(construction))
    (ROOT / "execution-manifest.json").write_text(encoded({
        "format": "worker-execution-manifest", "assignment_id": AID,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": records,
    }))
    print("built", len(records), "exact C111278 case bundles")


if __name__ == "__main__":
    build()
