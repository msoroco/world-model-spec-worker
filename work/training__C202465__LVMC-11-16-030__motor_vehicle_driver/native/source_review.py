"""Load original grade-crossing survey and exception-source review.

Schema-only fixtures exercise rejection paths. A local operator must provide
separately reviewed original sources before any physical recording is accepted.
"""

from __future__ import annotations

import hashlib
import json
from math import hypot, isfinite
from pathlib import Path

ROLES = ("railway", "approach", "flagman", "signal")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _numbers(values, n, label):
    if not isinstance(values, list) or len(values) != n:
        raise ValueError(label + " geometry missing")
    try:
        result = [float(v) for v in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(label + " geometry invalid") from exc
    if not all(isfinite(v) for v in result):
        raise ValueError(label + " geometry nonfinite")
    return result


def load(root, road_sha256, *, diagnostic_fixture=False):
    root = Path(root)
    if not isinstance(road_sha256, str) or len(road_sha256) != 64:
        raise ValueError("original road source hash required")
    records = {}
    for role in ROLES:
        path, source = root / (role + ".json"), root / (role + ".source.txt")
        if not path.is_file() or not source.is_file():
            raise ValueError("original grade-crossing review source missing: " + role)
        row = json.loads(path.read_text())
        if (row.get("role") != role or row.get("road_sha256") != road_sha256
                or row.get("source_sha256") != sha(source)
                or row.get("review_status") != ("schema_only" if diagnostic_fixture else "independently_reviewed")
                or row.get("provenance_kind") != ("synthetic_fixture" if diagnostic_fixture else "original_native")
                or not row.get("reviewer_id")):
            raise ValueError("original grade-crossing review differs: " + role)
        records[role] = row
    rail = records["railway"]
    if rail.get("crossing_kind") != "at_grade" or rail.get("railway_type") not in (
            "steam", "electric", "other_motor") or not rail.get("railway_identity"):
        raise ValueError("qualifying grade crossing and motor railway review required")
    _numbers(rail.get("crossing_xyz_m"), 3, "crossing")
    axis = _numbers(rail.get("rail_unit_direction_xy"), 2, "rail axis")
    if abs(hypot(*axis)-1.0) > 1e-6:
        raise ValueError("rail axis must be unit length")
    if rail.get("surveyed_left_extent_m", 0) < 121.92 or rail.get("surveyed_right_extent_m", 0) < 121.92:
        raise ValueError("both 400-foot surveyed railway extents required")
    vehicle_ids = rail.get("rail_vehicle_actor_ids")
    if (not isinstance(vehicle_ids, dict) or set(vehicle_ids) != {"left", "right"}
            or any(type(value) is not int or value <= 0 for value in vehicle_ids.values())
            or vehicle_ids["left"] == vehicle_ids["right"]):
        raise ValueError("two distinct original railway vehicle actor IDs required")
    approach = records["approach"]
    if (approach.get("driver_role") != "motor_vehicle_driver"
            or approach.get("municipal_jurisdiction_verified") is not True
            or approach.get("approach_maneuver") != "cross_railway"):
        raise ValueError("original driver, jurisdiction and crossing approach required")
    _numbers(approach.get("approach_direction_xy"), 2, "approach direction")
    if approach.get("surveyed_approach_length_m", 0) < 30.48:
        raise ValueError("last 100 feet of original approach not surveyed")
    _numbers(approach.get("ego_spawn_xyz_m"), 3, "ego spawn")
    if not isinstance(approach.get("ego_spawn_yaw_deg"), (int, float)):
        raise ValueError("original reviewed ego spawn heading required")
    flagman = records["flagman"]
    if (flagman.get("source_method") != "original_actor_and_duty_readback"
            or type(flagman.get("on_duty_at_capture_start")) is not bool):
        raise ValueError("original flagman identity and duty review required")
    signal = records["signal"]
    if (signal.get("source_method") != "original_device_visibility_and_state_readback"
            or any(type(signal.get(key)) is not bool for key in
                   ("installed", "clearly_visible", "indicates_immediate_approach"))):
        raise ValueError("original crossing signal identity, visibility and state required")
    return records
