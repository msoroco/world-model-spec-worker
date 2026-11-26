"""Saved original-source lane and overtaking observations for NRS 484B.270(2)(a).

Lane availability, reasonable safety and due care remain review questions. The
module never substitutes an engineering distance for those legal standards.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C228989__NRS-484B-270-2a__motor_vehicle_driver"
QUALIFYING = ("bicycle", "electric_bicycle", "electric_scooter")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _vector(v):
    if not isinstance(v, list) or len(v) != 2 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in v):
        raise ValueError("finite two-dimensional vector required")
    return v


def _body(vertices, origin, axis):
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError("eight original world-space body vertices required")
    station = []
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) != 3 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in vertex):
            raise ValueError("finite original body vertex required")
        station.append((vertex[0] - origin[0]) * axis[0] + (vertex[1] - origin[1]) * axis[1])
    return min(station), max(station)


def validate_context(context, case_id):
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source-hashed road context required")
    if context.get("ego_kind") != "motor_vehicle" or context.get("control_kind") not in QUALIFYING:
        raise ValueError("motor vehicle and qualifying cycle/scooter required")
    if not context.get("ego_driver_source") or not context.get("control_rider_source"):
        raise ValueError("driver and control rider identity sources required")
    origin, axis = _vector(context.get("road_origin")), _vector(context.get("road_forward"))
    if abs(math.hypot(*axis) - 1) > .02:
        raise ValueError("road-forward vector must have unit length")
    lanes = context.get("lanes")
    if not isinstance(lanes, list) or len(lanes) < 1:
        raise ValueError("source-backed lane inventory required")
    ids = [lane.get("lane_id") for lane in lanes]
    if any(not lane_id for lane_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("distinct original lane identities required")
    for lane in lanes:
        heading = _vector(lane.get("forward"))
        if abs(math.hypot(*heading) - 1) > .02 or not lane.get("source_ref"):
            raise ValueError("source-backed lane direction required")
    ego_lane = context.get("ego_initial_lane_id")
    if ego_lane not in ids or context.get("control_initial_lane_id") != ego_lane:
        raise ValueError("ego and qualifying control must start in same lane")
    by_id = {lane["lane_id"]: lane for lane in lanes}
    same_direction = [lane for lane in lanes if sum(a * b for a, b in zip(lane["forward"], axis)) > .9]
    if ego_lane not in {lane["lane_id"] for lane in same_direction}:
        raise ValueError("original ego lane direction mismatch")
    immediate_left = context.get("immediate_left_lane_id")
    if len(same_direction) > 1:
        if immediate_left not in by_id or immediate_left == ego_lane:
            raise ValueError("immediate-left lane identity required")
        if immediate_left not in {lane["lane_id"] for lane in same_direction}:
            raise ValueError("immediate-left lane must proceed same direction")
        if by_id[ego_lane].get("immediate_left_lane_id") != immediate_left:
            raise ValueError("left-lane adjacency source mismatch")
    elif immediate_left is not None:
        raise ValueError("single-lane context cannot claim immediate-left lane")
    for key in ("lane_restrictions_source", "left_lane_traffic_source", "left_lane_obstructions_source",
                "surrounding_trajectories_source"):
        if not context.get(key):
            raise ValueError("original lane availability context missing: " + key)
    return origin, axis, len(same_direction), immediate_left, {lane["lane_id"] for lane in same_direction}


def measure(*, case_id, context_path, trace_path, receipt_path,
            allow_diagnostic=False):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case ID required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture is not delivery evidence")
    if allow_diagnostic and receipt.get("diagnostic_fixture") is not True:
        raise ValueError("diagnostic processing requires marked synthetic fixture")
    if _sha(context_path) != receipt.get("context_sha256") or _sha(trace_path) != receipt.get("trace_sha256"):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    origin, axis, same_direction_lane_count, immediate_left, same_direction_ids = validate_context(context, case_id)
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    lane_ids = {lane["lane_id"] for lane in context["lanes"]}
    observations = []
    previous = None
    for row in rows:
        frame, time_s = row.get("frame"), row.get("time_s")
        if not isinstance(frame, int) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError("original frame/time missing")
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > .002):
            raise ValueError("original frame order or 20 Hz cadence mismatch")
        previous = frame, time_s
        ego_rear, ego_front = _body(row.get("ego_vertices"), origin, axis)
        control_rear, control_front = _body(row.get("control_vertices"), origin, axis)
        if row.get("ego_lane_id") not in lane_ids or row.get("control_lane_id") not in lane_ids:
            raise ValueError("original actor lane identity missing")
        if row["ego_lane_id"] not in same_direction_ids or row["control_lane_id"] not in same_direction_ids:
            raise ValueError("original actor lane direction differs from pass direction")
        if not observations and (row["ego_lane_id"] != context["ego_initial_lane_id"] or
                                 row["control_lane_id"] != context["control_initial_lane_id"]):
            raise ValueError("original initial actor lane mismatch")
        if not isinstance(row.get("left_lane_occupied_actor_ids"), list):
            raise ValueError("original left-lane occupancy inventory missing")
        for key in ("ego_speed_mps", "control_speed_mps"):
            if not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError("original actor speed missing")
        observations.append({"frame": frame, "time_s": time_s,
                             "ego_rear_station_m": ego_rear, "ego_front_station_m": ego_front,
                             "control_rear_station_m": control_rear, "control_front_station_m": control_front,
                             "ego_lane_id": row["ego_lane_id"], "control_lane_id": row["control_lane_id"],
                             "left_lane_occupied_actor_ids": row["left_lane_occupied_actor_ids"],
                             "ego_speed_mps": row["ego_speed_mps"], "control_speed_mps": row["control_speed_mps"]})
    if not (observations[0]["ego_front_station_m"] < observations[0]["control_rear_station_m"]):
        raise ValueError("control cycle/scooter must start ahead of ego")
    full_pass = [r for r in observations if r["ego_rear_station_m"] > r["control_front_station_m"]]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": _sha(context_path), "trace_sha256": _sha(trace_path),
                                "receipt_sha256": _sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "control_kind": context["control_kind"], "same_direction_lane_count": same_direction_lane_count,
            "immediate_left_lane_id": immediate_left,
            "first_observed_full_pass_frame": full_pass[0]["frame"] if full_pass else None,
            "ego_lane_at_full_pass": full_pass[0]["ego_lane_id"] if full_pass else None,
            "left_lane_occupied_at_full_pass": full_pass[0]["left_lane_occupied_actor_ids"] if full_pass else None,
            "observations": observations, "due_care_judgment": "unresolved",
            "lane_availability_judgment": "unresolved", "reasonable_safety_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(case_id=args.case, context_path=args.context,
                     trace_path=args.trace, receipt_path=args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
