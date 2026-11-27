"""Saved Native sample measurement proposal for NRS 484B.450(1)(k).

This measures geometry and traffic response. It does not make the statute's
judgment that traffic *would* be obstructed or prove CARLA execution.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Invalid finite number: " + label)
    return float(value)


def _rectangle(value: object, label: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("Missing sampled rectangle: " + label)
    left, bottom, right, top = (_number(v, label) for v in value)
    if not left < right or not bottom < top:
        raise ValueError("Invalid sampled rectangle: " + label)
    return left, bottom, right, top


def _overlap_x(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0]))


def _largest_open_width(road: tuple[float, ...], occupied: list[tuple[float, ...]]) -> float:
    intervals = sorted((max(road[1], r[1]), min(road[3], r[3])) for r in occupied)
    cursor = road[1]
    openings = []
    for low, high in intervals:
        if high <= low:
            continue
        openings.append(max(0.0, low - cursor))
        cursor = max(cursor, high)
    openings.append(max(0.0, road[3] - cursor))
    return max(openings)


def measure(path: Path, expected_sha256: str) -> dict:
    """Reject missing, changed, unsynchronized, or unsourced original rows."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing required source: native_samples.jsonl")
    actual_sha256 = sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError("Original Native source hash differs")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != 600:
        raise ValueError("Native sample count differs from 600")
    first = rows[0]
    road = _rectangle(first.get("road_xy_m"), "road_xy_m")
    obstruction = _rectangle(first.get("obstruction_xy_m"), "obstruction_xy_m")
    if first.get("obstruction_kind") not in ("excavation", "physical_obstruction"):
        raise ValueError("Highway obstruction kind not source confirmed")
    if not road[1] <= obstruction[1] < obstruction[3] <= road[3]:
        raise ValueError("Obstruction not inside sampled highway surface")
    widths = []
    ego_speeds = []
    traffic_speeds = []
    traffic_widths = []
    exception_flags = []
    alongside_frames = 0
    passing_halt_frames = 0
    passing_crossed_obstruction_x = False
    prior_traffic_center = None
    prior_traffic_speed = None
    native_start = rows[0].get("native_frame")
    if type(native_start) is not int or native_start < 0:
        raise ValueError("Original Native frame start missing")
    for index, row in enumerate(rows):
        if row.get("native_frame") != native_start + index or abs(_number(row.get("time_s"), "time_s") - index / 20) > 1e-7:
            raise ValueError("Native frame/time join differs")
        if row.get("road_xy_m") != first["road_xy_m"] or row.get("obstruction_xy_m") != first["obstruction_xy_m"] or row.get("obstruction_kind") != first["obstruction_kind"]:
            raise ValueError("Original highway obstruction geometry differs")
        ego = _rectangle(row.get("ego_body_xy_m"), "ego_body_xy_m")
        traffic = _rectangle(row.get("passing_body_xy_m"), "passing_body_xy_m")
        if not road[1] <= ego[1] < ego[3] <= road[3]:
            raise ValueError("Parked body not on sampled highway surface")
        speed = _number(row.get("ego_speed_m_s"), "ego_speed_m_s")
        other_speed = _number(row.get("passing_speed_m_s"), "passing_speed_m_s")
        if speed < 0 or other_speed < 0:
            raise ValueError("Negative sampled vehicle speed")
        traffic_center = (traffic[0] + traffic[2]) / 2
        if prior_traffic_center is not None:
            expected_displacement = (prior_traffic_speed + other_speed) / 40
            actual_displacement = traffic_center - prior_traffic_center
            if abs(actual_displacement - expected_displacement) > 0.03:
                raise ValueError("Passing body motion differs from sampled speed")
        prior_traffic_center = traffic_center
        prior_traffic_speed = other_speed
        if traffic_center >= obstruction[2]:
            passing_crossed_obstruction_x = True
        flags = row.get("exceptions")
        source = row.get("exception_source")
        if not isinstance(flags, dict) or set(flags) != {"traffic_conflict", "law_direction", "police_direction", "traffic_device"} or any(type(v) is not bool for v in flags.values()):
            raise ValueError("Exception flags incomplete")
        if source != {"traffic_conflict_reviewed": True, "law_direction_reviewed": True, "police_direction_reviewed": True, "traffic_device_reviewed": True}:
            raise ValueError("Exception source review incomplete")
        longitudinal_overlap = _overlap_x(ego, obstruction)
        if longitudinal_overlap > 0:
            alongside_frames += 1
        if speed <= 0.05 and longitudinal_overlap > 0:
            widths.append(_largest_open_width(road, [ego, obstruction]))
        ego_speeds.append(speed)
        traffic_speeds.append(other_speed)
        traffic_widths.append(traffic[3] - traffic[1])
        exception_flags.append(any(flags.values()))
        if other_speed <= 0.05:
            passing_halt_frames += 1
    if len(widths) < 400:
        raise ValueError("No sustained parked alongside obstruction sample")
    return {
        "source_sha256": actual_sha256,
        "frames": len(rows),
        "duration_s": 30.0,
        "obstruction_kind": first["obstruction_kind"],
        "alongside_frames": alongside_frames,
        "parked_alongside_frames": len(widths),
        "minimum_open_width_m": min(widths),
        "maximum_open_width_m": max(widths),
        "passing_body_width_m": max(traffic_widths),
        "passing_halt_frames": passing_halt_frames,
        "passing_crossed_obstruction_x": passing_crossed_obstruction_x,
        "minimum_passing_speed_m_s": min(traffic_speeds),
        "maximum_passing_speed_m_s": max(traffic_speeds),
        "exception_flags_all_false": not any(exception_flags),
        "legal_obstruction_verdict": "unresolved_requires_review",
        "physical_cause_confirmed": False,
    }
