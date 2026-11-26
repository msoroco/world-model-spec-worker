"""Independently compare exact island-side or circulation-lane saved attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha


def compare(comparison_id, plan, attempts, *, diagnostic=False):
    plan = json.loads(Path(plan).read_text(encoding="utf-8"))
    row = next((item for item in plan["comparisons"]
                if item["comparison_id"] == comparison_id), None)
    if row is None or len(row["case_ids"]) != 2 or len(attempts) != 2:
        raise ValueError("unknown exact two-case island comparison")
    audits = [audit(attempt, cid, diagnostic=diagnostic)
              for attempt, cid in zip(attempts, row["case_ids"])]
    packets = [json.loads(required(Path(attempt), "original-map.json").read_text(encoding="utf-8"))
               for attempt in attempts]
    fixed = ("map_sha256", "native_map_sha256", "map_name", "island",
             "circulation_surface_polygon", "circulation_lanes", "connected_route_source",
             "vehicle_driver_source", "ego_blueprint")
    for key in fixed:
        if packets[0].get(key) != packets[1].get(key):
            raise ValueError("fixed island comparison source changed: " + key)
    if audits[0]["trace_sha256"] == audits[1]["trace_sha256"]:
        raise ValueError("comparison needs distinct original vehicle traces")
    lane_roles = [packet.get("selected_lane_role") for packet in packets]
    sides = [packet.get("requested_island_side") for packet in packets]
    if comparison_id in ("inner_side", "outer_side"):
        expected_role = "inner" if comparison_id == "inner_side" else "outer"
        if lane_roles != [expected_role, expected_role] or sides != ["right", "left"]:
            raise ValueError("declared island-side variable differs")
        changed = "requested_island_side"
    elif comparison_id == "right_lane_choice":
        if sides != ["right", "right"] or lane_roles != ["inner", "outer"]:
            raise ValueError("declared circulation-lane variable differs")
        changed = "circulation_lane_role"
    else:
        raise ValueError("unknown island comparison variable")
    if not diagnostic and any(audit_row["decoded_images"] != 3600 for audit_row in audits):
        raise ValueError("comparison requires two full original four-camera attempts")
    return {"format": "worker-independent-island-comparison-audit",
        "comparison_id": comparison_id, "case_ids": row["case_ids"],
        "fixed_context_checked": True, "deliberate_difference_checked": True,
        "declared_variable": changed, "source_bound": True,
        "original_trace_sha256": [sha(required(Path(attempt), "original-trace.jsonl"))
                                  for attempt in attempts],
        "sampled_right_frames": [item["sampled_right_frames"] for item in audits],
        "sampled_left_or_overlap_frames": [item["sampled_left_or_overlap_frames"] for item in audits],
        "diagnostic_fixture": diagnostic, "physical_acceptance": False, "legal_verdict": None}


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
