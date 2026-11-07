"""Saved Native intersection-approach diagnostic for NRS 484B.603(1).

Thresholds below are engineering surrogates, not a statutory speed limit or
legal verdict. The source hash and complete pose/velocity series are required.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FPS = 20
FRAMES = 480
JUNCTION_ENTRY_Y_M = -7.0
JUNCTION_EXIT_Y_M = 7.0
APPROACH_START_Y_M = -60.0
APPROACH_END_Y_M = -20.0
MPS_TO_MPH = 2.2369362920544


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def measure(path: Path, expected_sha256: str) -> dict:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256 or len(expected_sha256) != 64:
        raise ValueError("Saved Native source hash changed")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except ValueError as exc:
        raise ValueError("Invalid saved Native JSONL") from exc
    if len(rows) != FRAMES:
        raise ValueError("Expected 480 complete Native frames")
    ids, sources, positions, speeds, other_positions, velocities = set(), set(), [], [], [], []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("frame") != i:
            raise ValueError("Noncontinuous Native frames")
        if abs(_number(row.get("t_s"), "timestamp") - i / FPS) > .001:
            raise ValueError("Native timestamp does not join 20 Hz frame")
        if row.get("ego_role") != "motor_vehicle_driver" or row.get("other_role") != "motor_vehicle_driver":
            raise ValueError("Frozen actor roles absent")
        if row.get("source_kind") == "original_native_capture":
            if (row.get("ego_role_name") != "c111294_approach_subject" or
                    row.get("other_role_name") != "c111294_cross_traffic" or
                    row.get("ego_blueprint") != "vehicle.tesla.model3" or
                    row.get("other_blueprint") != "vehicle.tesla.model3"):
                raise ValueError("Original Native actor readback differs")
        if row.get("ego_actor_id") == row.get("other_actor_id"):
            raise ValueError("Other vehicle identity absent")
        ids.add((row.get("ego_actor_id"), row.get("other_actor_id")))
        sources.add(row.get("source_kind"))
        pose, other, velocity = (row.get(key) for key in
                                 ("ego_position_m", "other_position_m", "ego_velocity_mps"))
        if any(not isinstance(v, list) or len(v) != 3 for v in (pose, other, velocity)):
            raise ValueError("Three-axis Native pose or velocity absent")
        p = tuple(_number(v, "ego pose") for v in pose)
        o = tuple(_number(v, "other pose") for v in other)
        v = tuple(_number(v, "ego velocity") for v in velocity)
        positions.append(p)
        other_positions.append(o)
        velocities.append(v)
        speeds.append(math.dist(v, (0, 0, 0)) * MPS_TO_MPH)
    if len(ids) != 1 or len(sources) != 1 or not sources <= {"synthetic_cpu_fixture", "original_native_capture"}:
        raise ValueError("Actor or source identity changed")
    direction = 1 if positions[-1][1] > positions[0][1] else -1
    ys = [direction*p[1] for p in positions]
    if ys[0] >= APPROACH_START_Y_M or ys[-1] <= JUNCTION_EXIT_Y_M:
        raise ValueError("Incomplete intersection approach and crossing")
    if any(b < a for a, b in zip(ys, ys[1:])):
        raise ValueError("Reverse ego path")
    if any(math.dist(tuple((b[j]-a[j])*FPS for j in range(3)), velocities[i]) > 3.0
           for i, (a, b) in enumerate(zip(positions, positions[1:]), 1)):
        raise ValueError("Saved pose and speed disagree")
    if max(abs(o[0]-other_positions[0][0]) for o in other_positions) < 10:
        raise ValueError("Other vehicle did not traverse approach")
    before = [s for y, s in zip(ys, speeds)
              if APPROACH_START_Y_M <= y < -50]
    after = [s for y, s in zip(ys, speeds)
             if APPROACH_END_Y_M <= y < JUNCTION_ENTRY_Y_M]
    crossing = [s for y, s in zip(ys, speeds)
                if JUNCTION_ENTRY_Y_M <= y <= JUNCTION_EXIT_Y_M]
    if min(map(len, (before, after, crossing))) < 3:
        raise ValueError("Approach or crossing window missing")
    start_mph = sum(before)/len(before)
    entry_mph = sum(after)/len(after)
    decrease = start_mph-entry_mph
    if decrease >= 3.0 and max(crossing) <= start_mph-2.0:
        relation = "measured_early_decrease_held"
    elif decrease < 1.0:
        relation = "measured_no_material_decrease"
    else:
        relation = "measured_ambiguous_decrease"
    return {"source_sha256": digest, "source_kind": next(iter(sources)),
            "frames": FRAMES, "rate_hz": FPS, "approach_start_mph": round(start_mph, 3),
            "measured_travel_direction_y": direction,
            "preentry_mph": round(entry_mph, 3), "decrease_mph": round(decrease, 3),
            "crossing_peak_mph": round(max(crossing), 3), "measured_relation": relation,
            "surrogate_thresholds_mph": {"material_decrease": 3, "held_reduction": 2},
            "physical_native_capture_verified": False, "legal_verdict": None}
