"""Independent, source-bound nighttime truck controlled comparison audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha

ROOT = Path(__file__).resolve().parent
FIELDS = ("target_district", "target_local_time", "target_permit_status",
          "target_street_class", "target_unladen_lb")
CHANGED = {
    "written_permit_vs_none": "target_permit_status",
    "application_only_vs_none": "target_permit_status",
    "route_condition_vs_valid": "target_permit_status",
    "time_condition_vs_valid": "target_permit_status",
    "truck_route_vs_nonroute": "target_street_class",
    "residence_vs_other": "target_district",
    "before_1900_vs_night": "target_local_time",
    "weight_below_vs_above": "target_unladen_lb",
    "weight_at_vs_above": "target_unladen_lb",
    "time_1900_vs_inside": "target_local_time",
    "time_before_0600_vs_inside": "target_local_time",
    "time_0600_vs_inside": "target_local_time",
}


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    declared = next((r for r in plan["comparisons"] if r["comparison_id"] == comparison_id), None)
    if declared is None or comparison_id not in CHANGED:
        raise ValueError("Unknown exact nighttime truck comparison")
    attempts = [first.resolve(), second.resolve()]
    reports = [audit(attempt, case_id, diagnostic) for attempt, case_id in
               zip(attempts, declared["case_ids"])]
    configs = [json.loads(required(attempt, "config.json").read_text()) for attempt in attempts]
    specs = [json.loads(required(attempt, "case-spec.json").read_text()) for attempt in attempts]
    packets = [json.loads(required(attempt, "original-night-truck-observations.json").read_text())
               for attempt in attempts]
    for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras"):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError("Fixed capture condition differs: " + field)
    varied = CHANGED[comparison_id]
    for field in FIELDS:
        values = [spec[field] for spec in specs]
        if (values[0] == values[1]) == (field == varied):
            raise ValueError("Declared contrast or fixed condition differs: " + field)
    if packets[0].get("assignment_id") != packets[1].get("assignment_id"):
        raise ValueError("Fixed assignment differs")
    if [row["road_id"] for row in packets[0]["frames"]] != [row["road_id"] for row in packets[1]["frames"]]:
        raise ValueError("Fixed original road path differs")
    if sha(attempts[0] / "original-night-truck-observations.json") == sha(attempts[1] / "original-night-truck-observations.json"):
        raise ValueError("Comparison reused one original source")
    return {"format": "worker-night-truck-comparison-audit", "comparison_id": comparison_id,
        "case_ids": declared["case_ids"], "passed": True, "diagnostic_only": diagnostic,
        "physical_acceptance": False, "legal_acceptance": False,
        "fixed_conditions": declared["fixed_conditions"],
        "deliberate_differences": declared["deliberate_differences"],
        "source_sha256": [sha(attempt / "original-night-truck-observations.json") for attempt in attempts],
        "frame_counts": [report["frame_count"] for report in reports]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    for attempt in (args.first_attempt, args.second_attempt):
        if args.output.resolve() == attempt.resolve() or attempt.resolve() in args.output.resolve().parents:
            raise ValueError("Comparison report must be outside original attempt")
    result = compare(args.comparison, args.first_attempt, args.second_attempt,
                     args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError("Retain prior comparison report")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": args.comparison, "passed": True,
                      "diagnostic_only": args.diagnostic_fixture}))


if __name__ == "__main__":
    main()
