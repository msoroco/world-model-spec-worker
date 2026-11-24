"""Source-bound right-turn-lane and junction observations for NRS 484B.223(4)(b)."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C376609__NRS-484B-223-4b__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original coordinate required")
    return value


def measure(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native capture required")
    if receipt.get("context_sha256") != sha(context_path) or receipt.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source map context required")
    for key in ("public_highway_source", "roadway_boundary_source", "lane_design_source",
                "exclusive_turn_control_source", "intersection_type_source", "intersection_boundary_source",
                "straight_route_source", "right_turn_route_source", "sightline_obstruction_source",
                "driver_identity_source", "motor_vehicle_source", "independent_route_intent_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    lane_ids = context.get("approach_lane_ids")
    if not isinstance(lane_ids, list) or not lane_ids or any(not isinstance(x, str) or not x for x in lane_ids) or len(set(lane_ids)) != len(lane_ids):
        raise ValueError("distinct original approach lane identities required")
    right_lane = context.get("right_turn_lane_id")
    if right_lane not in lane_ids:
        raise ValueError("original right turn lane identity required")
    entry = finite(context.get("intersection_entry_station_m"))
    exit_station = finite(context.get("intersection_exit_station_m"))
    if exit_station <= entry:
        raise ValueError("ordered original intersection boundaries required")
    if context.get("intersection_type") not in {"non_alley", "alley"}:
        raise ValueError("original intersection type required")
    if context.get("lane_design") not in {"exclusive_single_right", "nonexclusive_right", "multiple_right_turn_lanes"}:
        raise ValueError("original lane design required")
    if context.get("independent_route_intent") not in {"through", "right_turn", "stop_before"}:
        raise ValueError("independent route intent required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - index / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        lane = row.get("lane_id")
        if lane not in lane_ids:
            raise ValueError("original lane identity missing")
        station = finite(row.get("ego_station_m"))
        speed = finite(row.get("speed_mps"))
        if speed < 0:
            raise ValueError("original nonnegative speed required")
        if row.get("connected_route") not in {"through", "right_turn", "none"}:
            raise ValueError("original connected route required")
        observations.append({"frame": index, "time_s": row["time_s"], "ego_station_m": station,
                             "lane_id": lane, "speed_mps": speed, "connected_route": row["connected_route"],
                             "within_intersection_station_interval": entry <= station <= exit_station})
    if observations[0]["ego_station_m"] >= entry:
        raise ValueError("approach must begin before intersection")
    inside = [x for x in observations if x["within_intersection_station_interval"]]
    beyond = [x for x in observations if x["ego_station_m"] > exit_station]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "lane_design_source_label": context["lane_design"], "intersection_type_source_label": context["intersection_type"],
            "independent_route_intent": context["independent_route_intent"], "right_turn_lane_id": right_lane,
            "first_interval_frame": inside[0]["frame"] if inside else None,
            "first_beyond_exit_frame": beyond[0]["frame"] if beyond else None,
            "lane_at_first_interval_frame": inside[0]["lane_id"] if inside else None,
            "observations": observations, "travel_through_judgment": "unresolved",
            "exclusive_turn_lane_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
