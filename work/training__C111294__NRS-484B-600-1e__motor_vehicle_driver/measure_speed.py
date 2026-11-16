"""Source-bound saved Native speed measurement for NRS 484B.600(1)(e).

The statutory comparison is made against observed velocity, not a controller
request. This module does not decide territorial or other legal applicability.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FRAMES = 480
FPS = 20
MPS_TO_MPH = 2.2369362920544
LIMIT_MPH = 80.0


def _finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {field}")
    return float(value)


def measure(source_path: Path, expected_sha256: str, *, uncertainty_mph: float = 0.2) -> dict:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("Expected full source SHA-256")
    raw = Path(source_path).read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha256:
        raise ValueError("Saved Native source hash changed")
    uncertainty = _finite_number(uncertainty_mph, "uncertainty_mph")
    if not 0 < uncertainty <= 1:
        raise ValueError("Unsupported measurement uncertainty")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid Native JSONL") from exc
    if len(rows) != FRAMES:
        raise ValueError("Expected 480 complete Native frames")
    speeds = []
    ego_ids = set()
    other_ids = set()
    ego_positions = []
    other_positions = []
    velocities = []
    source_kinds = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("frame") != i:
            raise ValueError("Noncontinuous Native frame sequence")
        t = _finite_number(row.get("t_s"), "t_s")
        if abs(t - i / FPS) > 0.001:
            raise ValueError("Native timestamp does not join 20 Hz frame")
        ego_id = row.get("ego_actor_id")
        other_id = row.get("other_actor_id")
        if not isinstance(ego_id, int) or not isinstance(other_id, int) or ego_id == other_id:
            raise ValueError("Two distinct actor IDs required")
        ego_ids.add(ego_id)
        other_ids.add(other_id)
        if row.get("ego_role") != "motor_vehicle_driver" or row.get("other_role") != "motor_vehicle_driver":
            raise ValueError("Qualifying subject or other role missing")
        if row.get("ego_blueprint") != "vehicle.tesla.model3" or row.get("other_blueprint") != "vehicle.tesla.model3":
            raise ValueError("Declared conventional vehicle blueprint changed")
        kind = row.get("source_kind")
        if kind not in ("original_native_capture", "synthetic_cpu_fixture"):
            raise ValueError("Unknown Native source kind")
        source_kinds.add(kind)
        if kind == "original_native_capture" and (
                row.get("ego_role_name") != "c111294_speed_subject" or
                row.get("other_role_name") != "c111294_opposing_vehicle"):
            raise ValueError("Original actor role readback differs")
        control = row.get("ego_control")
        if not isinstance(control, dict) or set(control) != {"throttle", "brake", "steer"}:
            raise ValueError("Ego control source absent")
        if (any(not 0 <= _finite_number(control[name], "ego control") <= 1
                for name in ("throttle", "brake")) or
                not -1 <= _finite_number(control["steer"], "ego control") <= 1):
            raise ValueError("Ego control out of range")
        velocity = row.get("ego_velocity_mps")
        if not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError("Missing three-axis Native velocity")
        vx, vy, vz = (_finite_number(v, "velocity component") for v in velocity)
        speed = math.sqrt(vx * vx + vy * vy + vz * vz) * MPS_TO_MPH
        if speed > 150:
            raise ValueError("Implausible sample speed")
        speeds.append(speed)
        velocities.append((vx, vy, vz))
        pos = row.get("ego_position_m")
        other = row.get("other_position_m")
        if not isinstance(pos, list) or len(pos) != 3 or not isinstance(other, list) or len(other) != 3:
            raise ValueError("Missing actor position")
        ego_positions.append(tuple(_finite_number(v, "ego position") for v in pos))
        other_positions.append(tuple(_finite_number(v, "other position") for v in other))
    if len(ego_ids) != 1 or len(other_ids) != 1 or ego_ids == other_ids:
        raise ValueError("Actor identity changed within capture")
    if len(source_kinds) != 1:
        raise ValueError("Native source kind changed within capture")
    for previous, current, velocity in zip(ego_positions, ego_positions[1:], velocities[1:]):
        observed_delta = tuple((b - a) * FPS for a, b in zip(previous, current))
        if math.dist(observed_delta, velocity) > 5.0:
            raise ValueError("Velocity and pose path disagree")
    # Native import may reflect authored OpenDRIVE y. Accept either measured
    # travel direction, but require a complete crossing of the same junction.
    if not (abs(ego_positions[0][1]) > 7 and abs(ego_positions[-1][1]) > 7 and
            ego_positions[0][1] * ego_positions[-1][1] < 0):
        raise ValueError("Ego did not traverse authored intersection")
    if not abs(other_positions[0][1] - other_positions[-1][1]) > 100:
        raise ValueError("Separate other vehicle route or motion absent")
    if min(abs(a[0] - b[0]) for a, b in zip(ego_positions, other_positions)) < 3.4:
        raise ValueError("Opposing actors did not remain in distinct lanes")
    peak = max(speeds)
    lower = peak - uncertainty
    upper = peak + uncertainty
    if lower > LIMIT_MPH:
        relation = "measured_above_80_mph"
    elif upper <= LIMIT_MPH:
        relation = "measured_not_above_80_mph"
    else:
        relation = "unresolved_at_80_mph"
    return {"source_sha256": actual_sha, "frames": FRAMES, "rate_hz": FPS,
            "source_kind": next(iter(source_kinds)),
            "ego_actor_id": next(iter(ego_ids)), "other_actor_id": next(iter(other_ids)),
            "velocity_source": "saved Native three-axis ego velocity",
            "derived_peak_mph": round(peak, 6),
            "uncertainty_mph": uncertainty,
            "peak_interval_mph": [round(lower, 6), round(upper, 6)],
            "statutory_value_mph": LIMIT_MPH,
            "measured_relation": relation,
            "territorial_applicability_verified": False,
            "physical_native_capture_verified": False,
            "legal_verdict": None}


def synthetic_fixture(speed_mph: float) -> bytes:
    """CPU fixture only; never label this as original Native capture."""
    speed = _finite_number(speed_mph, "speed_mph") / MPS_TO_MPH
    if speed < 0:
        raise ValueError("Negative fixture speed")
    return "".join(json.dumps({
        "frame": i, "t_s": i / FPS,
        "ego_actor_id": 101, "other_actor_id": 202,
        "ego_role": "motor_vehicle_driver", "other_role": "motor_vehicle_driver",
        "ego_blueprint": "vehicle.tesla.model3",
        "other_blueprint": "vehicle.tesla.model3",
        "ego_position_m": [1.75, -70 + speed * i / FPS, 0],
        "other_position_m": [-1.75, 100 - 10 * i / FPS, 0],
        "ego_velocity_mps": [0, speed, 0],
        "ego_control": {"throttle": .5, "brake": 0, "steer": 0},
        "source_kind": "synthetic_cpu_fixture"}, sort_keys=True) + "\n"
        for i in range(FRAMES)).encode()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("sha256")
    args = parser.parse_args()
    print(json.dumps(measure(args.source, args.sha256), sort_keys=True))
