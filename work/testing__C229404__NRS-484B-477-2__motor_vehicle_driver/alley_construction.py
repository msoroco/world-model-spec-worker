"""Derive exact parking targets from source-surveyed alley and access geometry.

This generates an adapter request; it does not claim CARLA reached the targets.
The connected highway/alley status and parcel access need independent review.
"""
from __future__ import annotations

import math

from access_measurement import ASSIGNMENT, _overlap_area, _polygon


def _point(value, name):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError(name + " point missing")
    return (float(value[0]), float(value[1]))


def _body(center, axis, length, width):
    normal = (-axis[1], axis[0])
    return [[center[0] + sx * axis[0] * length / 2 + sy * normal[0] * width / 2,
             center[1] + sx * axis[1] * length / 2 + sy * normal[1] * width / 2]
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def build_plan(geometry: dict, case_id: str, *, direction: int = 1) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in {
            "driveway_clear", "driveway_overlap", "entrance_clear", "entrance_overlap"}:
        raise ValueError("unknown alley access case")
    if direction not in (-1, 1):
        raise ValueError("approach direction invalid")
    kind, position = suffix.split("_", 1)
    if geometry.get("access_kind") != kind:
        raise ValueError("access kind differs from exact case")
    if not all(geometry.get(k) for k in ("start_connection_source", "end_connection_source",
                                            "centerline_start_m", "centerline_end_m")):
        raise ValueError("connected alley endpoint evidence missing")
    a = _point(geometry["centerline_start_m"], "start")
    b = _point(geometry["centerline_end_m"], "end")
    vector = (b[0] - a[0], b[1] - a[1])
    distance = math.hypot(*vector)
    if distance < 80:
        raise ValueError("insufficient surveyed approach and departure length")
    axis = (vector[0] / distance, vector[1] / distance)
    access = _polygon(geometry.get("access_corridor_polygon_m"), "access corridor")
    projections = [(p[0] - a[0]) * axis[0] + (p[1] - a[1]) * axis[1] for p in access]
    middle = (min(projections) + max(projections)) / 2
    body_length = geometry.get("ego_length_m")
    body_width = geometry.get("ego_width_m")
    if (type(body_length) not in (int, float) or type(body_width) not in (int, float) or
            not 3.0 <= body_length <= 8.0 or not 1.0 <= body_width <= 3.0):
        raise ValueError("surveyed ego body dimensions invalid")
    # The clear target is beyond the projected access interval with a 2 m
    # engineering margin. The margin is not a legal definition of blocking.
    target_s = middle if position == "overlap" else max(projections) + body_length / 2 + 2.0
    start_s = target_s - direction * 30.0
    depart_s = target_s + direction * 15.0
    if not all(5 <= s <= distance - 5 for s in (start_s, target_s, depart_s)):
        raise ValueError("parking route leaves connected surveyed alley segment")
    at = lambda s: [round(a[0] + axis[0] * s, 6), round(a[1] + axis[1] * s, 6)]
    target = at(target_s)
    predicted_area = _overlap_area(_polygon(_body(target, axis, body_length, body_width),
                                             "planned body"), access)
    if position == "clear" and predicted_area > 1e-8:
        raise ValueError("clear parking target intrudes into access corridor")
    if position == "overlap" and predicted_area <= 0:
        raise ValueError("overlap target does not intersect surveyed access corridor")
    return {"case_id": case_id, "access_kind": kind, "parking_position": position,
            "direction": direction, "start_xy_m": at(start_s), "target_xy_m": target,
            "depart_xy_m": at(depart_s), "route_axis_xy": list(axis),
            "planned_body_polygon_m": _body(target, axis, body_length, body_width),
            "planned_access_intrusion_area_m2": round(predicted_area, 8),
            "controller": {"kind": "route_tracking_then_brake_and_hold",
                           "hold_min_s": 20.0, "target_tolerance_m": 0.5},
            "capture": {"rate_hz": 20, "duration_s": 45,
                        "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
            "statutory_blocking_judgment": "unresolved"}
