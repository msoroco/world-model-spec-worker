"""Independent measurement comparison; never labels legal prudence."""
from __future__ import annotations

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


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--comparison", required=True)
    p.add_argument("--left", type=Path, required=True)
    p.add_argument("--right", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(audit(json.loads(args.plan.read_text()), args.comparison,
                           json.loads(args.left.read_text()), json.loads(args.right.read_text()))))


if __name__ == "__main__":
    main()
