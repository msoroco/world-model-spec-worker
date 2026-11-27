"""Reopen a sealed 900-frame Native rail attempt and report measured facts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rail_saved_measurement import _source, verify_saved


def measure_traversal_sight(observation):
    return {key: observation[key] for key in (
        "crossing_original_frames", "approach_observation_frames",
        "all_three_sight_rays_clear_during_approach",
        "any_required_sight_ray_obstructed", "traversal_speed_mph_max",
        "traversal_speed_mph_min", "prima_facie_boundary_mph",
        "speed_boundary_relation_observed", "legal_visibility_judgment",
        "legal_speed_verdict")}


def measure_flagman(observation):
    return {"on_duty_flagman_observed":
            observation["exceptions"]["on_duty_flagman_observed"],
            "crossing_original_frames": observation["crossing_original_frames"]}


def measure_signal(observation):
    return {"clearly_visible_nonwarning_signal_observed":
            observation["exceptions"]["clearly_visible_nonwarning_signal_observed"],
            "clearly_visible_warning_signal_observed":
            observation["exceptions"]["clearly_visible_warning_signal_observed"],
            "crossing_original_frames": observation["crossing_original_frames"]}


METHODS = {"measure_traversal_sight": measure_traversal_sight,
           "measure_flagman": measure_flagman,
           "measure_signal": measure_signal}


def analyze(attempt, contract, case_id):
    attempt = Path(attempt).resolve()
    contract = json.loads(Path(contract).read_text())
    if contract.get("case_id") != case_id:
        raise ValueError("selected rail measurement contract identity differs")
    receipt_path = attempt / "native-rail-receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("Missing required source: native-rail-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    packet = json.loads(_source(attempt, receipt.get("packet")).read_text())
    for row in contract["requirements"]:
        for name in row["inputs"]:
            source = attempt / name
            if not source.is_file() or source.is_symlink():
                raise ValueError("Missing required source: " + name)
    if receipt.get("capture_kind") == "diagnostic_fixture":
        from rail_diagnostic_measurement import verify_diagnostic
        saved = verify_diagnostic(attempt, receipt, packet, case_id)
    else:
        saved = verify_saved(attempt, packet, case_id)
    observation = saved["observation"]
    values = {}
    for row in contract["requirements"]:
        method = row["method"]
        if method not in METHODS:
            raise ValueError("unknown railway measurement method")
        values[row["output_key"]] = {
            "method": method,
            "value": METHODS[method](observation),
            "sources": {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                        for name in row["inputs"]},
        }
    report = {"case_id": case_id, "source_complete": True,
              "measurements": values, "original_frame_count": 900,
              "camera_views": saved["camera_views"],
              "observation": observation,
              "diagnostic_fixture": saved.get("diagnostic_fixture", False),
              "physical_completion_confirmed": False,
              "legal_conclusion": None}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract = args.contract or args.attempt / "measurement-contract.json"
    config = json.loads((args.attempt / "config.json").read_text())
    case_id = args.case_id or config.get("selected_case_id")
    if args.case_id is not None and args.case_id != config.get("selected_case_id"):
        raise ValueError("selected railway case differs from materialized config")
    report = analyze(args.attempt, contract, case_id)
    target = args.output or args.attempt / "rail-analysis.json"
    if target.parent.resolve() != args.attempt.resolve() or target.name not in (
            "rail-analysis.json", "analysis-report.json"):
        raise ValueError("rail analysis output must remain in the saved attempt")
    if target.exists() or target.is_symlink():
        raise ValueError("rail analysis result already exists")
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if target.name == "analysis-report.json":
        from rail_media_finalize import finalize
        from rail_core_projection import project
        receipt = json.loads((args.attempt / "native-rail-receipt.json").read_text())
        packet = json.loads(_source(args.attempt, receipt["packet"]).read_text())
        if receipt.get("capture_kind") == "original_native":
            finalize(args.attempt, packet, case_id)
        project(args.attempt, packet, case_id, report["observation"])
    print(json.dumps({"case_id": case_id, "source_complete": True}))


if __name__ == "__main__":
    main()
