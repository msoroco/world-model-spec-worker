"""Independent measurement comparison; never labels legal prudence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


VARIABLE = {
    "speed_under_clear_conditions": "speed",
    "visibility_at_reference_speed": "visibility",
    "pedestrian_at_reference_speed": "pedestrians",
    "surface_at_reference_speed": "surface",
}


def audit(plan: dict, comparison_id: str, left: dict, right: dict) -> dict:
    comparison = next((row for row in plan["comparisons"] if row["comparison_id"] == comparison_id), None)
    if comparison is None or comparison_id not in VARIABLE:
        raise ValueError("unknown comparison")
    if [left.get("case_id"), right.get("case_id")] != comparison["case_ids"]:
        raise ValueError("comparison case identity mismatch")
    for record in (left, right):
        if record.get("source_kind") != "original_native" or record.get("legal_prudence") != "unresolved":
            raise ValueError("missing original measurement or judgment separation")
        if not record.get("samples") or any("speed_mps" not in row for row in record["samples"]):
            raise ValueError("missing speed history")
    variable = VARIABLE[comparison_id]
    context_fields = ("jurisdiction", "bicycle_classification", "alley_route", "rack_geometry")
    for field in context_fields:
        if field == variable:
            continue
        if left["context"].get(field) != right["context"].get(field):
            raise ValueError("fixed condition changed: " + field)
    if variable == "speed":
        a, b = left["summary"]["mean_speed_mps"], right["summary"]["mean_speed_mps"]
        if a == b:
            raise ValueError("measured speed did not differ")
    condition_fields = ("weather", "surface", "visibility", "pedestrians", "curvature")
    for field in condition_fields:
        if field != variable and [row[field] for row in left["condition_samples"]] != [row[field] for row in right["condition_samples"]]:
            raise ValueError("fixed condition changed: " + field)
    if variable != "speed" and [row[variable] for row in left["condition_samples"]] == [row[variable] for row in right["condition_samples"]]:
        raise ValueError("declared condition did not differ: " + variable)
    if len(left["samples"]) != len(right["samples"]) or [row["time_s"] for row in left["samples"]] != [row["time_s"] for row in right["samples"]]:
        raise ValueError("comparison frame/time coverage differs")
    if len(left["condition_samples"]) != len(left["samples"]) or len(right["condition_samples"]) != len(right["samples"]):
        raise ValueError("incomplete condition history")
    return {"format": "c10307-bicycle-speed-comparison-audit", "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"], "passed": True, "deliberate_variable": variable,
            "legal_prudence": "unresolved", "source_kind": "original_native"}


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_saved_pair(plan: dict, comparison_id: str, left_path: Path,
                     right_path: Path, left_receipt_path: Path,
                     right_receipt_path: Path) -> dict:
    """Bind both selected measurements to independent saved delivery audits."""
    paths = (Path(left_path), Path(right_path))
    receipt_paths = (Path(left_receipt_path), Path(right_receipt_path))
    records = [json.loads(path.read_text()) for path in paths]
    receipts = [json.loads(path.read_text()) for path in receipt_paths]
    required = {"native_source", "all_participants", "time_join", "full_video_decode",
                "actual_pixels", "physical_completion"}
    for record, receipt, path in zip(records, receipts, paths):
        if (receipt.get("format") != "worker-delivery-audit" or
                receipt.get("passed") is not True or
                receipt.get("case_id") != record.get("case_id") or
                not required <= set(receipt.get("checks", [])) or
                receipt.get("native_result_sha256") != _sha(path)):
            raise ValueError("comparison lacks source-bound independent delivery audit")
        if record.get("diagnostic_fixture") is True:
            raise ValueError("comparison cannot use diagnostic fixture")
    result = audit(plan, comparison_id, *records)
    result["measurement_sha256"] = [_sha(path) for path in paths]
    result["delivery_audit_sha256"] = [_sha(path) for path in receipt_paths]
    result["independent_delivery_audits"] = True
    return result


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--comparison", required=True)
    p.add_argument("--left", type=Path, required=True)
    p.add_argument("--right", type=Path, required=True)
    p.add_argument("--left-delivery-audit", type=Path)
    p.add_argument("--right-delivery-audit", type=Path)
    args = p.parse_args()
    plan = json.loads(args.plan.read_text())
    if bool(args.left_delivery_audit) != bool(args.right_delivery_audit):
        raise ValueError("both independent delivery audits are required")
    result = (audit_saved_pair(plan, args.comparison, args.left, args.right,
                               args.left_delivery_audit, args.right_delivery_audit)
              if args.left_delivery_audit else
              audit(plan, args.comparison,
                    json.loads(args.left.read_text()), json.loads(args.right.read_text())))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
