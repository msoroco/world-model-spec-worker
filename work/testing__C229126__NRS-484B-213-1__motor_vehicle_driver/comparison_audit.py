"""Independent source-bound comparison of two saved measurement reports.

This checks physical measurement isolation. It does not resolve NRS judgment phrases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FACTORS = {
    "visibility_clear_vs_occluded": ("left_ray_any_occluded",),
    "oncoming_far_vs_near": ("oncoming_forward_station_gap_m",),
    "approaching_response": ("oncoming_response",),
    "overtaken_response": ("overtaken_speed_mps",),
    "passing_completion": ("measured_pass_and_return_frame",),
}


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(plan, left, right, left_path, right_path, comparison_id):
    matches = [c for c in plan["comparisons"] if c["comparison_id"] == comparison_id]
    if len(matches) != 1:
        raise ValueError("unknown comparison")
    comparison = matches[0]
    if [left.get("case_id"), right.get("case_id")] != comparison["case_ids"]:
        raise ValueError("case identity or order mismatch")
    for report in (left, right):
        if report.get("format") != "nrs-484b-213-1-comparison-input":
            raise ValueError("wrong saved comparison input")
        if not report.get("native_result_sha256") or not report.get("measurement_sha256"):
            raise ValueError("missing original source bindings")
        if not report.get("physical_completion_reviewed"):
            raise ValueError("physical completion not reviewed")
        if not report.get("full_video_decode_reviewed"):
            raise ValueError("full original video decode not reviewed")
        if not report.get("actual_pixels_reviewed"):
            raise ValueError("actual pixels not reviewed")
        if not isinstance(report.get("fixed_conditions"), dict) or not report["fixed_conditions"]:
            raise ValueError("missing measured fixed conditions")
        if not isinstance(report.get("measured_differences"), dict):
            raise ValueError("missing measured differences")
    if left["fixed_conditions"] != right["fixed_conditions"]:
        raise ValueError("fixed conditions differ")
    factors = FACTORS[comparison_id]
    for factor in factors:
        if factor not in left["measured_differences"] or factor not in right["measured_differences"]:
            raise ValueError("missing declared difference measurement")
        if left["measured_differences"][factor] == right["measured_differences"][factor]:
            raise ValueError("declared difference not measured")
    return {"format": "worker-comparison-audit-draft", "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"], "left_report_sha256": _digest(left_path),
            "right_report_sha256": _digest(right_path), "checked_fixed_conditions": sorted(left["fixed_conditions"]),
            "checked_differences": list(factors), "judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.plan.read_text()), json.loads(args.left.read_text()),
                   json.loads(args.right.read_text()), args.left, args.right,
                   args.comparison)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
