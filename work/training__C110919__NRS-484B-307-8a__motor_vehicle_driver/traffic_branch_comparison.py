"""Independent full-body comparison for signal-directed other traffic."""
import hashlib
import json
import math
from pathlib import Path

POLICIES = ("traffic_yield_wait", "traffic_conflict_entry")
SHARED = ("native_frame", "time_s", "signal_state_observed",
          "other_traffic_center_xy_m", "other_traffic_body_xy_m",
          "other_traffic_speed_mps", "other_traffic_signal_state_observed",
          "traffic_conflict_occupied", "walker_center_xy_m",
          "walker_conflict_occupied")
MOTION = ("native_center_xy_m", "native_body_xy_m", "native_yaw_deg",
          "speed_mps", "controller_request", "traffic_decision_reason",
          "traffic_policy")
PHYSICAL = ("native_center_xy_m", "native_body_xy_m", "native_yaw_deg", "speed_mps")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(path: Path, digest: str):
    require(path.is_file() and sha(path) == digest, "Retained traffic source hash changed")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def in_zone(body):
    require(isinstance(body, list) and len(body) == 4 and
            all(isinstance(vertex, list) and len(vertex) == 2 and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in vertex) for vertex in body),
            "Native full-body footprint missing")
    return (max(v[0] for v in body) >= 8 and min(v[0] for v in body) <= 12 and
            max(v[1] for v in body) >= -4 and min(v[1] for v in body) <= 4)


def measure(samples, policy):
    require(policy in POLICIES and len(samples) == 480,
            "Exact traffic policy or 480 Native samples missing")
    previous = -1
    crossing = None
    stopped, occupied, ego_entries, overlaps = [], [], [], []
    for index, row in enumerate(samples):
        frame, time, speed = (row.get(name) for name in
                              ("native_frame", "time_s", "speed_mps"))
        require(type(frame) is int and frame > previous and
                type(time) in (int, float) and math.isfinite(time) and
                type(speed) in (int, float) and math.isfinite(speed) and speed >= 0,
                "Native frame, time or ego speed invalid")
        previous = frame
        require(row.get("traffic_policy") == policy and
                row.get("signal_state_observed") in ("Red", "TrafficLightState.Red") and
                row.get("other_traffic_signal_state_observed") in
                ("Green", "TrafficLightState.Green"),
                "Shared red stop or directed green traffic state absent")
        traffic = row.get("other_traffic_body_xy_m")
        observed = in_zone(traffic)
        require(row.get("traffic_conflict_occupied") is observed and
                type(row.get("other_traffic_speed_mps")) in (int, float) and
                math.isfinite(row["other_traffic_speed_mps"]) and
                row["other_traffic_speed_mps"] >= 0,
                "Traffic full-body occupancy or speed differs")
        ego = row.get("native_body_xy_m")
        ego_occupied = in_zone(ego)
        if observed:
            occupied.append(index)
        if ego_occupied:
            ego_entries.append(index)
            if observed:
                overlaps.append(index)
        front = max(vertex[1] for vertex in ego)
        if crossing is None and front >= -14:
            crossing = index
        if speed <= .05 and front < -14:
            stopped.append(index)
    require(crossing is not None and occupied and ego_entries,
            "Stop-boundary crossing or moving traffic conflict absent")
    prior = [index for index in stopped if index < crossing]
    longest = span = 0
    last = -2
    for index in prior:
        span = span + 1 if index == last + 1 else 1
        longest = max(longest, span)
        last = index
    require(longest >= 10, "Shared full-body red-signal stop absent")
    return {"first_front_crossing_frame": crossing,
            "stationary_pre_crossing_frames": longest,
            "first_ego_body_conflict_frame": ego_entries[0],
            "first_other_traffic_conflict_frame": occupied[0],
            "last_other_traffic_conflict_frame": occupied[-1],
            "body_traffic_overlap_frames": overlaps}


def compare(wait_samples, entry_samples, *, diagnostic):
    require(type(diagnostic) is bool, "Provenance mode invalid")
    if diagnostic:
        require(all(row.get("synthetic_diagnostic") is True and
                    row.get("speed_provenance") == "synthetic_native_sample"
                    for group in (wait_samples, entry_samples) for row in group),
                "Synthetic traffic source provenance missing")
    else:
        require(all(row.get("synthetic_diagnostic") is not True and
                    row.get("speed_provenance") != "synthetic_native_sample"
                    for group in (wait_samples, entry_samples) for row in group),
                "Diagnostic traffic source cannot be original")
    wait = measure(wait_samples, POLICIES[0])
    entry = measure(entry_samples, POLICIES[1])
    different = []
    for index, (left, right) in enumerate(zip(wait_samples, entry_samples)):
        require(all(left.get(key) == right.get(key) for key in SHARED),
                "Held frame, signal, actor or pedestrian context differs")
        require(set(left) == set(right) and
                {key for key in left if left[key] != right[key]} <= set(MOTION),
                "Undeclared paired source difference")
        if any(left[key] != right[key] for key in PHYSICAL):
            different.append(index)
    require(different and min(different) >= wait["first_other_traffic_conflict_frame"] and
            wait["body_traffic_overlap_frames"] == [] and
            entry["body_traffic_overlap_frames"] and
            wait["first_ego_body_conflict_frame"] >
            wait["last_other_traffic_conflict_frame"] and
            entry["first_ego_body_conflict_frame"] <=
            entry["last_other_traffic_conflict_frame"],
            "Controlled signal-directed traffic/body contrast absent")
    return {"format": "c110919-traffic-branch-saved-comparison-v1",
            "cases": list(POLICIES), "wait": wait, "entry": entry,
            "different_frame_range": [min(different), max(different)],
            "source_comparison_passed": True, "diagnostic_fixture": diagnostic,
            "original_delivery_accepted": False, "legal_verdict_claimed": False}
