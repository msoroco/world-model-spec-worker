"""Independent prospective audit of selected lane-change comparisons.

The diagnostic mode CPU-tests source joins and comparison isolation. Native
acceptance requires each exact case's separate sealed delivery audit receipt.
Measured gaps remain engineering observations, never legal cutoffs.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or not Path(output_root).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
from delivery_acceptance import CHECKS, audit_sources, read, sha, verify_physical, verify_seal  # noqa: E402


VARIABLES = {
    "signal_order": {"signal_timing", "indicator_direction", "appropriate_signal_lead_frames"},
    "target_lane_gap": {"target_vehicle_placement", "nearest_target_body_gap_at_departure_m"},
    "lane_change_direction": {"lane_change_direction", "indicator_direction"},
    "signal_departure_boundary": {"signal_timing", "appropriate_signal_lead_frames"},
    "signal_lead_finite_sweep": {"appropriate_signal_lead_frames"},
    "target_gap_finite_sweep": {"nearest_target_body_gap_at_departure_m"},
}
SIGNAL = {"signal_order", "signal_departure_boundary", "signal_lead_finite_sweep"}
GAP = {"target_lane_gap", "target_gap_finite_sweep"}


def prove(comparison_id, index_path, diagnostic=False):
    comparison = next((row for row in read(HERE / "case-plan.json")["comparisons"]
                       if row["comparison_id"] == comparison_id), None)
    if comparison is None or comparison_id not in VARIABLES:
        raise ValueError("Unknown selected comparison")
    case_ids = comparison["case_ids"]
    if len(case_ids) < 2 or len(case_ids) != len(set(case_ids)):
        raise ValueError("Comparison case inventory differs")
    proposal = {row["case_id"]: row for row in read(HERE / "proposals/cases.json")["cases"]}
    index = read(index_path)
    if set(index.get("attempts", {})) != set(case_ids):
        raise ValueError("Comparison index omits or adds an exact case")
    rows = []
    for case_id in case_ids:
        attempt = Path(index["attempts"][case_id]).resolve()
        result = read(attempt / "result.json")
        if result.get("case_id") != case_id:
            raise ValueError("Comparison result selects another case")
        if diagnostic:
            if result.get("provenance_kind") != "synthetic_fixture" or result.get("diagnostic_fixture") is not True:
                raise ValueError("Diagnostic source provenance differs")
        else:
            if result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is not False:
                raise ValueError("Native source provenance required")
            verify_seal(attempt)
            receipt_path = Path(index.get("delivery_receipts", {}).get(case_id, ""))
            receipt = read(receipt_path)
            if (receipt.get("format") != "worker-c144550-delivery-audit"
                    or receipt.get("case_id") != case_id or receipt.get("passed") is not True
                    or receipt.get("diagnostic_fixture") is not False
                    or receipt.get("checks") != {key: True for key in CHECKS}
                    or receipt.get("auditor_sha256") != sha(HERE / "delivery_acceptance.py")
                    or not receipt.get("pixel_review_sha256")
                    or receipt.get("physical_acceptance_claimed") is not False
                    or receipt.get("capture_seal_sha256") != sha(attempt / "capture-seal.json")
                    or receipt.get("owner_release_sha256") != sha(attempt / "owner-release.json")
                    or receipt.get("source_audit", {}).get("lane_history_sha256") != sha(attempt / "lane_history.jsonl")):
                raise ValueError("Accepted independent delivery receipt missing or stale")
        source_audit = audit_sources(attempt, case_id)
        verify_physical(result, attempt)
        report = read(attempt / "analysis-report.json")
        if report.get("case_id") != case_id:
            raise ValueError("Comparison analysis selects another case")
        source_hashes = report.get("source_hashes", {})
        for name in ("lane_context.json", "lane_history.jsonl", "video_frames.jsonl"):
            if source_hashes.get(name) != sha(attempt / name):
                raise ValueError("Comparison analysis source changed: " + name)
        value = report.get("measurements", {}).get("signal_and_gap_at_movement", {}).get("value", {})
        gap = value.get("nearest_target_body_longitudinal_gap_at_movement_m")
        if (not isinstance(gap, (int, float)) or not math.isfinite(gap) or gap < 0
                or type(value.get("appropriate_signal_before_movement")) is not bool
                or value.get("indicator_at_movement") not in ("left", "right", "off")):
            raise ValueError("Comparison realized source measurement missing")
        config = read(attempt / "config.json")
        fixed_config = {key: config.get(key) for key in ("law_id", "cell_id", "actor", "duration_s", "rate_hz", "cameras")}
        assignments = {key: item.get("value") for key, item in proposal[case_id]["variable_assignments"].items()}
        rows.append({"case_id": case_id, "attempt": str(attempt), "fixed_config": fixed_config,
                     "lane_context": read(attempt / "lane_context.json"),
                     "assignments": assignments, "observed": value,
                     "original_frames": source_audit["original_frame_count"],
                     "source_sha256": {name: sha(attempt / name) for name in
                                       ("lane_context.json", "lane_history.jsonl", "video_frames.jsonl",
                                        "trace.jsonl", "capture/evidence.jsonl")}})
    baseline = rows[0]
    allowed = VARIABLES[comparison_id]
    for item in rows[1:]:
        if item["fixed_config"] != baseline["fixed_config"] or item["original_frames"] != baseline["original_frames"]:
            raise ValueError("Comparison fixed capture contract differs")
        if comparison_id != "lane_change_direction" and item["lane_context"] != baseline["lane_context"]:
            raise ValueError("Comparison fixed lane geometry differs")
        if {key: value for key, value in item["assignments"].items() if key not in allowed} != {
                key: value for key, value in baseline["assignments"].items() if key not in allowed}:
            raise ValueError("Comparison changed undeclared setup or controller variable")
    varied = {key for key in allowed if len({json.dumps(item["assignments"].get(key), sort_keys=True)
                                           for item in rows}) > 1}
    if not varied:
        raise ValueError("Comparison has no deliberate variable change")
    if comparison_id in SIGNAL:
        observed = {(item["observed"]["indicator_at_movement"],
                     item["observed"]["appropriate_signal_before_movement"]) for item in rows}
        if len(observed) < 2:
            raise ValueError("Original signal contrast did not occur")
    elif comparison_id in GAP:
        gaps = [item["observed"]["nearest_target_body_longitudinal_gap_at_movement_m"] for item in rows]
        planned = [item["assignments"]["nearest_target_body_gap_at_departure_m"] for item in rows]
        if len(set(gaps)) < 2 or (gaps[0] < gaps[-1]) != (planned[0] < planned[-1]):
            raise ValueError("Original target-body gap contrast did not occur")
    else:
        if {item["lane_context"].get("change_direction") for item in rows} != {"left", "right"}:
            raise ValueError("Original lane-change direction contrast did not occur")
    return {"format": "worker-c144550-native-comparison-audit", "comparison_id": comparison_id,
            "case_ids": case_ids, "diagnostic_fixture": diagnostic, "passed": not diagnostic,
            "fixed_conditions_checked": comparison["fixed_conditions"],
            "deliberate_variables": sorted(varied),
            "observed": {item["case_id"]: item["observed"] for item in rows},
            "original_source_sha256": {item["case_id"]: item["source_sha256"] for item in rows},
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    receipt = prove(args.comparison, args.index, args.diagnostic)
    if args.output:
        if args.output.exists():
            raise ValueError("Comparison audit receipt must be new")
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))
