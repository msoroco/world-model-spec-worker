"""Independently compare original yield reference hierarchy and safety contrasts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha
from yield_measure import measure


def compare(comparison_id, plan, attempts, *, diagnostic=False):
    plan = json.loads(Path(plan).read_text(encoding="utf-8"))
    row = next((item for item in plan["comparisons"]
                if item["comparison_id"] == comparison_id), None)
    if row is None or len(row["case_ids"]) != len(attempts):
        raise ValueError("unknown or incomplete exact yield comparison")
    audits = [audit(attempt, cid, diagnostic=diagnostic)
              for attempt, cid in zip(attempts, row["case_ids"])]
    packets = [json.loads(required(Path(attempt), "original-yield-site.json").read_text(encoding="utf-8"))
               for attempt in attempts]
    measured = [measure(attempt, cid) for attempt, cid in zip(attempts, row["case_ids"])]
    for key in ("assignment_id", "map_id", "control", "yield_sign_id", "vehicle_type",
                "intersecting_highway_id", "approach_roadway_id", "intersecting_highway_boundary_x",
                "approaching_traffic_points", "occluders", "driver_viewpoint_candidates"):
        if any(packet.get(key) != packets[0].get(key) for packet in packets[1:]):
            raise ValueError("fixed yield comparison source changed: " + key)
    kinds = [item["reference"]["reference_kind"] for item in measured]
    stops = [item["original_stop_samples"] for item in measured]
    if comparison_id == "nearest_view_vs_earlier_obscured":
        if (len(attempts) != 2 or kinds != ["nearest_point_with_geometric_view"] * 2 or
                [packet["stopping_required_for_safety"] for packet in packets] != ["yes", "yes"] or
                not all(stops) or min(row["distance_to_reference_m"] for row in stops[0]) >=
                min(row["distance_to_reference_m"] for row in stops[1])):
            raise ValueError("declared nearest-view versus earlier obscured stop differs")
        changed = "original_stop_position"
    elif comparison_id == "stop_reference_hierarchy":
        if (len(attempts) != 3 or kinds != ["nearest_point_with_geometric_view",
                "marked_stop_line", "nearest_crosswalk"] or not all(stops) or
                packets[0]["nearest_crosswalk_position"] is not None or
                packets[0]["marked_stop_line_position"] is not None or
                packets[1]["nearest_crosswalk_position"] is not None or
                packets[1]["marked_stop_line_position"] is None or
                packets[2]["nearest_crosswalk_position"] is None):
            raise ValueError("declared crosswalk/line/view hierarchy differs")
        changed = "source_crosswalk_and_marked_line_inventory"
    elif comparison_id == "conditional_safety_necessity":
        if (len(attempts) != 2 or kinds != ["nearest_point_with_geometric_view"] * 2 or
                [packet["stopping_required_for_safety"] for packet in packets] != ["yes", "no"] or
                not stops[0] or stops[1]):
            raise ValueError("declared source safety necessity and stop behavior differ")
        changed = "independently_sourced_safety_necessity_and_stop_behavior"
    else:
        raise ValueError("unknown exact yield comparison variable")
    if not diagnostic and any(item["decoded_images"] != 3600 for item in audits):
        raise ValueError("comparison requires full original four-camera attempts")
    return {"format": "worker-independent-yield-comparison-audit",
        "comparison_id": comparison_id, "case_ids": row["case_ids"],
        "fixed_context_checked": True, "deliberate_difference_checked": True,
        "declared_variable": changed, "source_bound": True,
        "original_trace_sha256": [sha(required(Path(attempt), "original-yield-trace.jsonl"))
                                  for attempt in attempts],
        "reference_kinds": kinds, "stop_sample_counts": [len(rows) for rows in stops],
        "diagnostic_fixture": diagnostic, "physical_acceptance": False,
        "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("refusing to overwrite comparison audit")
    result = compare(args.comparison_id, args.plan, args.attempt, diagnostic=args.diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"comparison_id": args.comparison_id,
                      "case_ids": result["case_ids"], "diagnostic_fixture": args.diagnostic}))


if __name__ == "__main__":
    main()
