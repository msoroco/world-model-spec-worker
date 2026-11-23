"""Source-bound, value-free alley-operation measurements.

This module records exterior vehicle behavior. It never infers a driver's mental
state or a legal outcome from yaw, acceleration, spacing, or lane position.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("frame", "time_s", "person_id", "vehicle_id", "operating",
            "position_x_m", "position_y_m", "yaw_rate_rad_s", "speed_m_s",
            "accel_longitudinal_m_s2", "hard_deceleration",
            "straddles_marking", "time_to_conflict_s", "traffic_signal")


def measure(path: Path, expected_case_id: str) -> dict:
    source = path.read_bytes()
    if not source:
        raise ValueError("missing source: empty operation history")
    rows = [json.loads(line) for line in source.splitlines()]
    if len(rows) < 2:
        raise ValueError("operation history needs two source frames")
    first = rows[0]
    person, vehicle = first.get("person_id"), first.get("vehicle_id")
    if not person or not vehicle:
        raise ValueError("person and vehicle identities required")
    prior_time = -math.inf
    for index, row in enumerate(rows):
        missing = set(REQUIRED) - row.keys()
        if missing:
            raise ValueError("missing source fields: " + ", ".join(sorted(missing)))
        if row.get("case_id") != expected_case_id:
            raise ValueError("exact case identity mismatch")
        if row["frame"] != index or row["person_id"] != person or row["vehicle_id"] != vehicle:
            raise ValueError("frame or participant identity discontinuity")
        time = row["time_s"]
        if not isinstance(time, (float, int)) or not math.isfinite(time) or time <= prior_time:
            raise ValueError("nonmonotonic source time")
        prior_time = time
        if type(row["operating"]) is not bool or type(row["hard_deceleration"]) is not bool or type(row["straddles_marking"]) is not bool:
            raise ValueError("Boolean observation has wrong type")
        for key in ("position_x_m", "position_y_m", "yaw_rate_rad_s", "speed_m_s", "accel_longitudinal_m_s2"):
            if not isinstance(row[key], (float, int)) or not math.isfinite(row[key]):
                raise ValueError("nonfinite observation: " + key)
        ttc = row["time_to_conflict_s"]
        if ttc is not None and (not isinstance(ttc, (float, int)) or not math.isfinite(ttc) or ttc < 0):
            raise ValueError("invalid time to conflict")
        if row["traffic_signal"] not in ("none", "red", "amber", "green", "unknown"):
            raise ValueError("unsupported traffic signal observation")
    active = [r for r in rows if r["operating"]]
    if not active:
        raise ValueError("no observed operating interval")
    return {
        "format": "worker-alley-operation-measurement",
        "case_id": expected_case_id,
        "source": {"path": str(path), "sha256": hashlib.sha256(source).hexdigest()},
        "person_id": person, "vehicle_id": vehicle,
        "operating_interval_s": [active[0]["time_s"], active[-1]["time_s"]],
        "frame_count": len(rows), "operating_frame_count": len(active),
        "observed_exterior": {
            "max_abs_yaw_rate_rad_s": max(abs(r["yaw_rate_rad_s"]) for r in active),
            "y_position_range_m": [min(r["position_y_m"] for r in active), max(r["position_y_m"] for r in active)],
            "speed_range_m_s": [min(r["speed_m_s"] for r in active), max(r["speed_m_s"] for r in active)],
            "accel_longitudinal_range_m_s2": [min(r["accel_longitudinal_m_s2"] for r in active), max(r["accel_longitudinal_m_s2"] for r in active)],
            "hard_deceleration_frames": sum(r["hard_deceleration"] for r in active),
            "straddles_marking_frames": sum(r["straddles_marking"] for r in active),
            "finite_time_to_conflict_s": [r["time_to_conflict_s"] for r in active if r["time_to_conflict_s"] is not None],
            "traffic_signal_states": sorted({r["traffic_signal"] for r in active}),
        },
        "attention_state": "unobserved",
        "legal_judgment": "unresolved",
        "limitations": ["Exterior kinematics and devices do not establish full time and attention.",
                        "Municipal applicability and vehicle-operation definition require source review."],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.source, args.case)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
