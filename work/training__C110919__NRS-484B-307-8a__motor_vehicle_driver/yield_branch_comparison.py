"""Independent saved-sample comparison for the unselected C110919 yield pair.

This reports physical sample overlap and stop timing, not a legal yield verdict.
Original acceptance requires separate Native, video and operations review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

POLICIES = ("yield_wait", "yield_conflict_entry")
SHARED = ("native_frame", "time_s", "walker_center_xy_m",
          "walker_conflict_occupied", "signal_state_observed")
MOTION = ("native_center_xy_m", "native_body_xy_m", "native_yaw_deg",
          "speed_mps", "controller_request", "yield_decision_reason",
          "yield_policy")
PHYSICAL_MOTION = ("native_center_xy_m", "native_body_xy_m", "native_yaw_deg",
                   "speed_mps")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(path: Path, expected_sha256: str):
    require(path.is_file() and sha(path) == expected_sha256,
            "Retained Native source hash missing or changed")
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def body_reaches_conflict(row):
    body = row.get("native_body_xy_m")
    require(isinstance(body, list) and len(body) == 4 and
            all(isinstance(vertex, list) and len(vertex) == 2 and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in vertex) for vertex in body),
            "Full-body Native footprint missing")
    xs = [vertex[0] for vertex in body]
    ys = [vertex[1] for vertex in body]
    return max(xs) >= 8 and min(xs) <= 12 and max(ys) >= -4 and min(ys) <= 4


def measure(samples, policy):
    require(policy in POLICIES and len(samples) == 480,
            "Exact policy or full 480-frame Native interval missing")
    previous = -1
    stopped = []
    crossing = None
    occupied = []
    overlaps = []
    entries = []
    for index, row in enumerate(samples):
        frame = row.get("native_frame")
        time = row.get("time_s")
        speed = row.get("speed_mps")
        require(type(frame) is int and frame > previous and
                type(time) in (int, float) and math.isfinite(time) and
                type(speed) in (int, float) and math.isfinite(speed) and speed >= 0,
                "Native frame, time or speed invalid")
        previous = frame
        require(row.get("yield_policy") == policy and
                row.get("signal_state_observed") in ("Red", "TrafficLightState.Red") and
                row.get("synthetic_diagnostic") is not False,
                "Policy, steady red or provenance differs")
        walker = row.get("walker_center_xy_m")
        require(isinstance(walker, list) and len(walker) == 2 and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in walker), "Walker Native center missing")
        observed_occupied = 8 <= walker[0] <= 12 and -4 <= walker[1] <= 4
        require(row.get("walker_conflict_occupied") is observed_occupied,
                "Walker occupancy flag differs from Native center")
        in_zone = body_reaches_conflict(row)
        if observed_occupied:
            occupied.append(index)
        if in_zone:
            entries.append(index)
            if observed_occupied:
                overlaps.append(index)
        front = max(vertex[1] for vertex in row["native_body_xy_m"])
        if crossing is None and front >= -14:
            crossing = index
        if speed <= .05 and front < -14:
            stopped.append(index)
    require(crossing is not None and occupied and entries,
            "Stop-boundary crossing or participant conflict absent")
    prior = [i for i in stopped if i < crossing]
    longest = span = 0
    last = -2
    for index in prior:
        span = span + 1 if index == last + 1 else 1
        longest = max(longest, span)
        last = index
    require(longest >= 10, "Shared red-signal full-body stop absent")
    return {"first_front_crossing_frame": crossing,
            "stationary_pre_crossing_frames": longest,
            "first_body_conflict_frame": entries[0],
            "first_pedestrian_conflict_frame": occupied[0],
            "last_pedestrian_conflict_frame": occupied[-1],
            "body_pedestrian_overlap_frames": overlaps}


def compare(wait_samples, entry_samples, *, diagnostic):
    require(type(diagnostic) is bool, "Provenance mode invalid")
    if diagnostic:
        require(all(row.get("synthetic_diagnostic") is True and
                    row.get("speed_provenance") == "synthetic_native_sample"
                    for group in (wait_samples, entry_samples) for row in group),
                "Synthetic source promoted or provenance missing")
    else:
        require(all(row.get("synthetic_diagnostic") is not True and
                    row.get("speed_provenance") != "synthetic_native_sample"
                    for group in (wait_samples, entry_samples) for row in group),
                "Diagnostic source cannot be treated as original")
    wait = measure(wait_samples, POLICIES[0])
    entry = measure(entry_samples, POLICIES[1])
    differences = []
    for index, (left, right) in enumerate(zip(wait_samples, entry_samples)):
        require(all(left.get(key) == right.get(key) for key in SHARED),
                "Held Native frame, signal or pedestrian context differs")
        require(set(left) == set(right) and
                {key for key in left if left[key] != right[key]} <= set(MOTION),
                "Undeclared paired source difference")
        if any(left[key] != right[key] for key in PHYSICAL_MOTION):
            differences.append(index)
    require(differences and min(differences) >= wait["first_pedestrian_conflict_frame"] and
            wait["body_pedestrian_overlap_frames"] == [] and
            entry["body_pedestrian_overlap_frames"] and
            wait["first_body_conflict_frame"] > wait["last_pedestrian_conflict_frame"] and
            entry["first_body_conflict_frame"] <= entry["last_pedestrian_conflict_frame"],
            "Controlled body/pedestrian occupancy contrast absent")
    return {"format": "c110919-yield-branch-saved-comparison-v1",
            "cases": list(POLICIES), "wait": wait, "entry": entry,
            "different_frame_range": [min(differences), max(differences)],
            "source_comparison_passed": True, "diagnostic_fixture": diagnostic,
            "original_delivery_accepted": False, "legal_verdict_claimed": False}
