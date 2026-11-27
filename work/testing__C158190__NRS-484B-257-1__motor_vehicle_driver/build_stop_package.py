"""Materialize the fixed stop-sign CPU bundle for the two exact C158190 cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
COMMON = (
    "runner.py", "analysis.py", "carla_yield_operator.py", "yield_scene_construction.py",
    "yield_view_measurement.py", "through_motion_measurement.py", "native_capture.py",
    "native_output_bridge.py", "saved_finalizer.py", "physical_completion.py",
    "stop_runner.py", "stop_sign_branch.py", "carla_stop_operator.py", "stop_native_capture.py",
    "stop_native_output_bridge.py", "stop_saved_finalizer.py", "stop_physical_completion.py",
    "stop_view_measurement.py", "stop_analysis.py", "case-plan.json",
)
TESTS = ("tests/test_stop_sign_branch.py", "tests/test_stop_view_measurement.py")
CHANNELS = ("stop_sign_and_marking", "nearest_view_stations", "ego_motion_and_crossing",
            "through_vehicle_motion", "governing_control", "original_four_camera_pixels")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    original = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    ids = [case["case_id"] for case in plan["cases"]]
    if ids != [ASSIGNMENT + "__stop_nearest_view_response",
               ASSIGNMENT + "__stop_nearest_view_uninterrupted"]:
        raise ValueError("fixed stop case plan differs")
    record = {
        "channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                      "time_window": "all 900 original frames", "reference_frame": "reviewed original stop intersection",
                      "method": "source-sealed original Native readback",
                      "uncertainty": "reviewed site and physical stop outcome pending"}
                     for name in CHANNELS],
        "context_inputs": [{"name": "reviewed_stop_site_source", "unit": "source",
                            "method": "independent SHA-256 reviewed stop sign, marking, route and view survey"}],
        "limitations": ["Immediate hazard and right of way have no invented numeric legal cutoff.",
                        "Stop-at-view geometry and through-traffic timing require original Native review."],
    }
    cameras = [{"name": name, "width": width, "height": height, "fov_deg": 80,
                "pose_strategy": "reviewed stop sign, nearest view and through highway sightline"}
               for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))]
    base = {"assignment_id": ASSIGNMENT, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "duration_s": 45, "rate_hz": 20, "cameras": cameras,
            "supported_case_ids": ids, "required_atoms": [], "source_packets": [],
            "plan_sha256": sha((ROOT / "case-plan.json").read_bytes()),
            "stop_brake_distance_multiplier": 1.0}
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()),
                "status": "partial_source_pending", "cases": []}
    for ordinal, case in enumerate(plan["cases"]):
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        config = {**base, "selected_case_id": case_id,
                  "case": {"case_id": case_id, "recording_description": record}}
        folder = ROOT / "cases" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        write(folder / "config-materialized.json", config)
        if ordinal == 0:
            write(ROOT / "config.json", config)
        config_text = (ROOT / "config.json").read_text() if ordinal == 0 else (folder / "config-materialized.json").read_text()
        files = [{"path": name, "content": (ROOT / name).read_text()} for name in COMMON + TESTS]
        files.append({"path": "config.json", "content": config_text})
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"], "actor": plan["actor"],
            "case_id": case_id, "entrypoint": "runner.py", "files": files,
            "measurement_plan": {"case_id": case_id, "procedure": "analysis.py",
                                 "source_packets": ["reviewed_original_stop_site", "original_context",
                                                    "original_trace", "original_camera_manifest"],
                                 "legal_judgment": "unresolved"},
            "recording_description": record,
            "mechanisms": ["reviewed fixed stop-sign control", "no stop line/crosswalk survey",
                           "sampled nearest-view rays", "source-sealed Native through traffic",
                           "four synchronized RGB cameras"],
            "static_checks": ["exact assignment/plan hash", "independent reviewed source bytes",
                              "900-frame 20 Hz four-view protocol"],
            "termination_rules": ["stop on source or Native readback mismatch",
                                  "restore Native settings and destroy owned actors"],
            "status": "source_gated_incomplete",
        }
        target = ROOT / "construction.json" if ordinal == 0 else folder / "construction.json"
        write(target, construction)
        fallback_config = {**config, "stop_brake_distance_multiplier": 1.5}
        fallback_construction = dict(construction)
        fallback_construction["files"] = [
            {"path": item["path"], "content": json.dumps(fallback_config, indent=2, sort_keys=True,
                                                            ensure_ascii=False) + "\n"}
            if item["path"] == "config.json" else item for item in files
        ]
        fallback_target = folder / "fallback1-construction.json"
        write(fallback_target, fallback_construction)
        contract = {
            "format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{"disposition_index": 0,
                              "requirement": plan["requirement_dispositions"][0]["requirement"],
                              "source": "NRS 484B.257(1)", "kind": "measured", "method": "measure",
                              "output_key": "nearest_view_stop_event", "value_type": "object",
                              "inputs": ["context.json", "original-trace.jsonl", "receipt.json", "cameras.json"]}],
            "negative": {"remove": ["context.json"],
                         "error_contains": "Missing required source: context.json"},
        }
        write(folder / "measurement-contract.json", contract)
        manifest["cases"].append({
            "case_id": case_id, "kind": "delivery", "status": "source_pending",
            "construction": str(target.relative_to(ROOT)), "construction_sha256": sha(target.read_bytes()),
            "measurement_contract": str((folder / "measurement-contract.json").relative_to(ROOT)),
            "measurement_procedure": {"entrypoint": "analysis.py",
                                      "method": "source-bound original stop-at-view and through-motion measurement"},
            "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(REPO)),
            "candidate_risk": {"status": "physical",
                               "reason": "Native braking may overshoot the sampled nearest-view station; original body and ray readback must decide."},
            "candidates": [{"id": "fallback1", "construction": str(fallback_target.relative_to(ROOT)),
                            "construction_sha256": sha(fallback_target.read_bytes()),
                            "trigger": {"source": "original Native body trace",
                                        "metric": "distance of complete stop from nearest visible station",
                                        "failure_condition": "primary stop overshoots the reviewed station by more than 0.5 m"},
                            "changed_knobs": ["stop_brake_distance_multiplier: 1.0 to 1.5"]}],
            "missing_proofs": ["reviewed_stop_site", "offline", "positive_negative_compatibility",
                               "saved_only_original", "original_delivery_acceptance", "original_comparison_audit"],
        })
    write(ROOT / "execution-manifest.json", manifest)
    print("stop bundles:", len(manifest["cases"]))


if __name__ == "__main__":
    build()
