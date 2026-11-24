"""Saved source speed meter for the C230222 80 mph comparison.

The meter reports a measured relation, never a legal verdict. A requested
controller speed is not evidence of achieved Native speed.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
HZ = 20
MPH_PER_MPS = 2.2369362920544
LIMIT_MPH = 80.0


def finite(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Invalid " + name)
    return float(value)


def measure(path: Path, expected_sha256: str, *, uncertainty_mph: float = 0.25) -> dict:
    """Check complete 30 s Native rows and measure the maximum vector speed."""
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Saved source hash changed")
    uncertainty = finite(uncertainty_mph, "uncertainty_mph")
    if uncertainty <= 0 or uncertainty > 1:
        raise ValueError("Unsupported measurement uncertainty")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (TypeError, ValueError) as exc:
        raise ValueError("Malformed saved Native JSONL") from exc
    if len(rows) != FRAMES:
        raise ValueError("Expected 600 complete Native frames")
    speeds = []
    previous = None
    actor_ids = set()
    source_kinds = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or type(row.get("frame")) is not int or row["frame"] != index:
            raise ValueError("Discontinuous Native frame sequence")
        if abs(finite(row.get("time_s"), "time_s") - index / HZ) > 1e-4:
            raise ValueError("Native timestamp does not join frame")
        if row.get("cell_id") != "C230222" or row.get("actor") != "motor_vehicle_driver":
            raise ValueError("Saved assignment identity changed")
        actor_id = row.get("ego_actor_id")
        if type(actor_id) is not int:
            raise ValueError("Missing subject actor ID")
        actor_ids.add(actor_id)
        kind = row.get("source_kind")
        if kind not in ("original_native_capture", "synthetic_native_sample"):
            raise ValueError("Unrecognized Native source kind")
        source_kinds.add(kind)
        position = row.get("ego_position_m")
        velocity = row.get("ego_velocity_mps")
        if not isinstance(position, list) or len(position) != 3 or not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError("Missing saved pose or three-axis velocity")
        position = tuple(finite(value, "position component") for value in position)
        velocity = tuple(finite(value, "velocity component") for value in velocity)
        if previous is not None:
            displacement_velocity = tuple((a - b) * HZ for a, b in zip(position, previous))
            if math.dist(displacement_velocity, velocity) > 1.0:
                raise ValueError("Saved pose and velocity disagree")
        previous = position
        speed = math.sqrt(sum(value * value for value in velocity)) * MPH_PER_MPS
        if speed > 150:
            raise ValueError("Implausible measured speed")
        speeds.append(speed)
    if len(actor_ids) != 1 or len(source_kinds) != 1:
        raise ValueError("Subject or source kind changed during capture")
    peak = max(speeds)
    lower, upper = peak - uncertainty, peak + uncertainty
    relation = ("measured_above_80_mph" if lower > LIMIT_MPH else
                "measured_not_above_80_mph" if upper <= LIMIT_MPH else
                "unresolved_at_80_mph")
    return {"format": "c230222-saved-speed-measurement-v1", "source_sha256": digest,
            "source_kind": next(iter(source_kinds)), "actor_id": next(iter(actor_ids)),
            "frames": FRAMES, "rate_hz": HZ, "duration_s": FRAMES / HZ,
            "source_fields": ["ego_position_m", "ego_velocity_mps"],
            "peak_speed_mph": round(peak, 6), "uncertainty_mph": uncertainty,
            "peak_interval_mph": [round(lower, 6), round(upper, 6)],
            "statutory_value_mph": LIMIT_MPH, "measured_relation": relation,
            "territorial_applicability_verified": False, "physical_completion": False,
            "legal_verdict": None, "accepted": False}


def synthetic_fixture(speed_mph: float) -> bytes:
    """Diagnostic Native-shaped rows, never original CARLA evidence."""
    velocity = finite(speed_mph, "speed_mph") / MPH_PER_MPS
    if velocity < 0:
        raise ValueError("Negative fixture speed")
    return "".join(json.dumps({"frame": index, "time_s": index / HZ,
        "cell_id": "C230222", "actor": "motor_vehicle_driver", "ego_actor_id": 101,
        "ego_position_m": [velocity * index / HZ, 0, 0],
        "ego_velocity_mps": [velocity, 0, 0],
        "source_kind": "synthetic_native_sample"}, sort_keys=True) + "\n"
        for index in range(FRAMES)).encode()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("sha256")
    arguments = parser.parse_args()
    print(json.dumps(measure(arguments.source, arguments.sha256), sort_keys=True))
