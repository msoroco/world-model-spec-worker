"""Independent original-source audit of side, facing and approach contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha

HERE = Path(__file__).resolve().parent


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    declared = next((row for row in plan["comparisons"] if row["comparison_id"] == comparison_id), None)
    if declared is None or len(declared["case_ids"]) != 2:
        raise ValueError("unknown exact walking comparison")
    attempts = [Path(first).resolve(), Path(second).resolve()]
    reports = [audit(attempt, case_id, diagnostic) for attempt, case_id in zip(attempts, declared["case_ids"])]
    packets = [json.loads(required(attempt, "original-walking-observations.json").read_text(encoding="utf-8")) for attempt in attempts]
    specs = [json.loads(required(attempt, "case-spec.json").read_text(encoding="utf-8")) for attempt in attempts]
    configs = [json.loads(required(attempt, "config.json").read_text(encoding="utf-8")) for attempt in attempts]
    a, b = packets
    if a.get("assignment_id") != b.get("assignment_id") or a.get("site_source_sha256") != b.get("site_source_sha256") or a.get("site") != b.get("site"):
        raise ValueError("fixed original highway site differs")
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras", "required_atoms"):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError("fixed walking capture configuration differs: " + key)
    if reports[0]["frame_count"] != reports[1]["frame_count"]:
        raise ValueError("comparison original frame counts differ")
    if sha(attempts[0] / "original-walking-observations.json") == sha(attempts[1] / "original-walking-observations.json"):
        raise ValueError("comparison reused one original walking source")
    id_parts = comparison_id.split("_")
    if comparison_id.endswith("_approach_side"):
        if (specs[0]["approach_direction"] != specs[1]["approach_direction"]
                or specs[0]["pedestrian_heading"] != specs[1]["pedestrian_heading"]
                or [spec["pedestrian_highway_side"] for spec in specs] != ["left", "right"]):
            raise ValueError("declared walking side contrast differs")
        for row_a, row_b in zip(a["frames"], b["frames"]):
            if diagnostic and (row_a["vehicle_xyz_m"] != row_b["vehicle_xyz_m"]
                    or row_a["vehicle_forward_xy"] != row_b["vehicle_forward_xy"]
                    or row_a["pedestrian_forward_xy"] != row_b["pedestrian_forward_xy"]
                    or row_a["pedestrian_xyz_m"][0] != row_b["pedestrian_xyz_m"][0]):
                raise ValueError("fixed source-shaped side comparison motion differs")
        if reports[0]["measurement"]["pedestrian_side_history"] == reports[1]["measurement"]["pedestrian_side_history"]:
            raise ValueError("measured pedestrian side contrast absent")
        branch = "pedestrian_highway_side"
    elif comparison_id.endswith("_approach_facing"):
        if (specs[0]["approach_direction"] != specs[1]["approach_direction"]
                or [spec["pedestrian_heading"] for spec in specs] != ["facing", "with_traffic"]
                or [spec["pedestrian_highway_side"] for spec in specs] != ["left", "left"]):
            raise ValueError("declared walking facing contrast differs")
        for row_a, row_b in zip(a["frames"], b["frames"]):
            if diagnostic and (row_a["vehicle_xyz_m"] != row_b["vehicle_xyz_m"]
                    or row_a["vehicle_forward_xy"] != row_b["vehicle_forward_xy"]
                    or row_a["pedestrian_xyz_m"][1] != row_b["pedestrian_xyz_m"][1]):
                raise ValueError("fixed source-shaped facing comparison motion differs")
        if reports[0]["measurement"]["all_frames_facing"] == reports[1]["measurement"]["all_frames_facing"]:
            raise ValueError("measured pedestrian facing contrast absent")
        branch = "pedestrian_heading"
    elif comparison_id == "approach_direction":
        if ([spec["approach_direction"] for spec in specs] != ["east", "west"]
                or any(spec["pedestrian_highway_side"] != "left" or spec["pedestrian_heading"] != "facing" for spec in specs)):
            raise ValueError("declared opposite approach contrast differs")
        if a["frames"][0]["vehicle_forward_xy"][0] * b["frames"][0]["vehicle_forward_xy"][0] >= 0:
            raise ValueError("opposite original approach directions absent")
        branch = "approach_direction"
    else:
        raise ValueError("unsupported exact walking comparison")
    return {"format": "worker-comparison-audit", "comparison_id": comparison_id,
        "case_ids": declared["case_ids"], "passed": True, "diagnostic_only": diagnostic,
        "physical_acceptance": False, "fixed_conditions": declared["fixed_conditions"],
        "deliberate_differences": declared["deliberate_differences"],
        "measured_difference": branch,
        "source_sha256": [sha(attempt / "original-walking-observations.json") for attempt in attempts],
        "frame_counts": [report["frame_count"] for report in reports]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    if any(attempt.resolve() == args.output.resolve() or attempt.resolve() in args.output.resolve().parents
           for attempt in (args.first_attempt, args.second_attempt)):
        raise ValueError("comparison report must be outside original attempt")
    result = compare(args.comparison, args.first_attempt, args.second_attempt, args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError("retain prior comparison report")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"comparison_id": args.comparison, "passed": True}))


if __name__ == "__main__":
    main()
