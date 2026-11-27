"""Independent source-bound controlled comparison of exact school-pass cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from school_pass import ASSIGNMENT, case_name


HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "case-plan.json").read_text())
ALLOWED = {
    "pass_activation": {"pass_requested"},
    "zone_extent": {"ego_route_xy", "pass_location"},
    "school_session": {"school_in_session"},
    "after_end_lower_boundary": {"local_datetime"},
    "after_end_upper_probe": {"local_datetime"},
    "before_start_lower_probe": {"local_datetime"},
    "before_start_upper_boundary": {"local_datetime"},
    "class_beacon_indication": {"lamp_state_samples", "beacon_flashing"},
    "sign_without_operational_beacon": {
        "zone_designated_by_operational_beacon", "beacon_operational",
        "lamp_state_samples", "sign_limit_active"},
}
FIXED = (
    "driver_id", "ego_id", "target_id", "ego_vehicle_class", "target_vehicle_class",
    "same_direction", "designated_zone_polygon_xy", "school_property_polygon_xy",
    "zone_designation_kind", "school_property_adjacency_reviewed", "target_route_xy",
    "target_route_lane_ids", "ego_route_lane_ids", "passing_lane_direction",
    "target_lane_direction", "pass_start_frame", "pass_end_frame",
)
TIMING_FIXED = (
    "last_operation_end", "next_operation_start", "class_start", "class_end",
    "beacon_yellow_light_count", "beacon_alternating_flash_capable",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(case_id: str, attempt: Path) -> tuple[dict, dict, dict]:
    case_name(case_id)
    attempt = Path(attempt)
    context_path = attempt / "context.json"
    report_path = attempt / "analysis-report.json"
    receipt_path = attempt / "receipt.json"
    for path in (context_path, report_path, receipt_path,
                 attempt / "original-trace.jsonl", attempt / "cameras.json"):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing required source: " + path.name)
    context = json.loads(context_path.read_text())
    report = json.loads(report_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if context.get("case_id") != case_id or report.get("case_id") != case_id or receipt.get("case_id") != case_id:
        raise ValueError("comparison exact-case source identity differs")
    hashes = {name: sha(attempt / name) for name in
              ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")}
    for measured in report.get("measurements", {}).values():
        if measured.get("sources") != hashes:
            raise ValueError("comparison selected measurement source changed")
    return context, report, hashes


def audit(comparison_id: str, left_case: str, left_attempt: Path,
          right_case: str, right_attempt: Path) -> dict:
    rows = [row for row in PLAN["comparisons"] if row["comparison_id"] == comparison_id]
    if len(rows) != 1 or rows[0]["case_ids"] != [left_case, right_case]:
        raise ValueError("exact planned comparison pair required")
    left, left_report, left_hashes = load(left_case, left_attempt)
    right, right_report, right_hashes = load(right_case, right_attempt)
    allowed = ALLOWED[comparison_id]
    differences = []
    for field in FIXED:
        if left.get(field) != right.get(field):
            if field not in allowed:
                raise ValueError("comparison fixed condition changed: " + field)
            differences.append(field)
    if left.get("ego_route_xy") != right.get("ego_route_xy"):
        if "ego_route_xy" not in allowed:
            raise ValueError("comparison fixed condition changed: ego_route_xy")
        differences.append("ego_route_xy")
    if left.get("pass_requested") != right.get("pass_requested"):
        if "pass_requested" not in allowed:
            raise ValueError("comparison fixed condition changed: pass_requested")
        differences.append("pass_requested")
    lt, rt = left["timing_packet"], right["timing_packet"]
    for field in TIMING_FIXED:
        if lt.get(field) != rt.get(field):
            raise ValueError("comparison fixed school/device context changed: " + field)
    for field in ("local_datetime", "school_in_session", "zone_designated_by_operational_beacon",
                  "beacon_operational", "lamp_state_samples", "sign_limit_active"):
        if lt.get(field) != rt.get(field):
            if field not in allowed:
                raise ValueError("comparison undeclared school/device difference: " + field)
            differences.append(field)
    if not differences:
        raise ValueError("comparison declared difference was not observed")
    # Source fixtures prove the audit algorithm and controlled requested inputs only.
    # Actual completed passes, zone pixels and exception application remain local review.
    return {"format": "worker-comparison-audit", "assignment_id": ASSIGNMENT,
            "comparison_id": comparison_id, "case_ids": [left_case, right_case],
            "fixed_conditions_checked": list(FIXED) + list(TIMING_FIXED),
            "declared_differences_observed": sorted(set(differences)),
            "source_hashes": {left_case: left_hashes, right_case: right_hashes},
            "diagnostic_fixture": bool(left_report.get("diagnostic_fixture") or right_report.get("diagnostic_fixture")),
            "physical_comparison_complete": False, "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left-case", required=True)
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-case", required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.left_case, args.left_attempt,
                   args.right_case, args.right_attempt)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
