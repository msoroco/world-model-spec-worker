"""Recompute measured school-crossing-zone heavy vehicle speed from sealed original Native frames."""

import json
import statistics
from pathlib import Path

from crossing_scene import load_case
from crossing_observations import measure

FRAMES = 900
STABLE_START = 200
STABLE_END = 800


def finalize(case_id, context_path, trace_path, receipt_path):
    case = load_case(case_id)
    observed = measure(case_id, context_path, trace_path, receipt_path)
    rows = observed["observations"]
    if len(rows) != FRAMES or rows[0]["frame"] != 0 or rows[-1]["frame"] != FRAMES - 1:
        raise ValueError("complete original 900-frame school-crossing-zone capture required")
    stable = rows[STABLE_START:STABLE_END]
    if len(stable) != STABLE_END - STABLE_START:
        raise ValueError("steady-state speed sample window incomplete")
    zone = [row for row in stable if row["inside_designated_zone"]]
    selected = zone if case["zone_request"] == "inside" else [
        row for row in stable if not row["inside_designated_zone"]]
    if len(selected) < 400:
        raise ValueError("steady-state selected-zone occupancy incomplete")
    if case["zone_request"] == "outside" and zone:
        raise ValueError("outside-zone control entered designated zone")
    speeds = [row["heavy_speed_mph"] for row in selected]
    median = statistics.median(speeds)
    p95 = sorted(speeds)[int(.95 * (len(speeds) - 1))]
    target = case["speed_target_mph"]
    return {"assignment_id": observed["assignment_id"], "case_id": case_id,
            "source_bindings": observed["source_bindings"],
            "stable_sample_window_frames": [STABLE_START, STABLE_END],
            "steady_state_selected_zone_sample_count": len(selected),
            "steady_state_heavy_speed_mph_median": median,
            "steady_state_heavy_speed_mph_p95": p95,
            "target_speed_mph": target,
            "engineering_target_within_0_25_mph": abs(median - target) <= .25,
            "school_session_source_fact": observed["school_in_session_today_source_fact"],
            "operational_beacon_designation_source_fact":
                observed["operational_beacon_designation_source_fact"],
            "maximum_observed_inside_zone_mph": observed["maximum_observed_inside_zone_mph"],
            "legal_exception_judgment": "unresolved",
            "legal_speed_rule_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = finalize(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
