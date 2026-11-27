"""Measure continuous original alley width; leave legal free movement for review.

The statutory 10-foot boundary is exact. This module measures physical free
cross-section intervals from surveyed boundaries and original body polygons. It
does not decide whether a vehicle could move freely or an ordinance applies.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C135705__NRS-484B-477-1b__motor_vehicle_driver"
FEET_PER_M = 3.280839895013123


def _point(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError(label + " must have two finite coordinates")
    return (float(value[0]), float(value[1]))


def _polygon(value, label):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(label + " polygon missing")
    return [_point(p, label) for p in value]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _inside(point, polygon):
    inside = False
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            crossing_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if crossing_x > x:
                inside = not inside
    return inside


def _blocked_interval(left, right, polygon):
    """Return cross-section parameters inside a polygon, including tangencies."""
    direction = (right[0] - left[0], right[1] - left[1])
    lengthsq = direction[0] ** 2 + direction[1] ** 2
    if lengthsq <= 1e-8:
        raise ValueError("alley cross-section has zero width")
    hits = []
    if _inside(left, polygon):
        hits.append(0.0)
    if _inside(right, polygon):
        hits.append(1.0)
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        edge = (b[0] - a[0], b[1] - a[1])
        offset = (a[0] - left[0], a[1] - left[1])
        determinant = _cross(direction, edge)
        if abs(determinant) < 1e-12:
            if abs(_cross(offset, direction)) < 1e-9:
                hits.extend(((a[0] - left[0]) * direction[0] +
                             (a[1] - left[1]) * direction[1]) / lengthsq for _ in (0,))
                hits.append(((b[0] - left[0]) * direction[0] +
                             (b[1] - left[1]) * direction[1]) / lengthsq)
            continue
        along = _cross(offset, edge) / determinant
        on_edge = _cross(offset, direction) / determinant
        if -1e-9 <= on_edge <= 1 + 1e-9 and -1e-9 <= along <= 1 + 1e-9:
            hits.append(max(0.0, min(1.0, along)))
    if not hits:
        return None
    return (min(hits), max(hits))


def continuous_free_width_m(left, right, bodies):
    left, right = _point(left, "left boundary"), _point(right, "right boundary")
    span = math.dist(left, right)
    intervals = []
    for i, body in enumerate(bodies):
        hit = _blocked_interval(left, right, _polygon(body, "body " + str(i)))
        if hit is not None and hit[1] > hit[0]:
            intervals.append(hit)
    intervals.sort()
    cursor = 0.0
    gaps = []
    for low, high in intervals:
        if low > cursor:
            gaps.append((cursor, low))
        cursor = max(cursor, high)
    if cursor < 1.0:
        gaps.append((cursor, 1.0))
    return span * max((high - low for low, high in gaps), default=0.0)


def _require_source(value, label):
    if not isinstance(value, dict) or not value.get("path") or not isinstance(value.get("sha256"), str) or len(value["sha256"]) != 64:
        raise ValueError(label + " source hash missing")


def measure(case_id, geometry, history, *, expected_frames=900):
    if not case_id.startswith(ASSIGNMENT + "__") or geometry.get("case_id") != case_id:
        raise ValueError("wrong exact alley-width identity")
    if geometry.get("alley_kind") != "other_alley":
        raise ValueError("any other alley source classification missing")
    for key in ("public_highway_source", "city_block_source", "rear_access_source",
                "abutting_property_source", "through_connection_source", "jurisdiction_source",
                "ordinance_source", "survey_source"):
        _require_source(geometry.get(key), key)
    if geometry.get("cul_de_sac") is not False or geometry.get("start_connected") is not True or geometry.get("end_connected") is not True:
        raise ValueError("connected non-cul-de-sac alley not established")
    if geometry.get("ordinance_status") not in ("none_found", "otherwise_provides", "unresolved"):
        raise ValueError("reviewed ordinance status missing")
    sections = geometry.get("cross_sections")
    if not isinstance(sections, list) or len(sections) < 2:
        raise ValueError("surveyed alley cross-sections missing")
    stations = []
    for section in sections:
        if type(section.get("station_m")) not in (int, float):
            raise ValueError("cross-section station missing")
        _point(section.get("left_xy_m"), "left boundary")
        _point(section.get("right_xy_m"), "right boundary")
        _require_source(section.get("source"), "cross-section")
        stations.append(float(section["station_m"]))
    if stations != sorted(set(stations)):
        raise ValueError("cross-section stations must be unique and ordered")
    if not isinstance(history, list) or len(history) != expected_frames:
        raise ValueError("original 20 Hz frame history incomplete")
    if [r.get("frame") for r in history] != list(range(history[0].get("frame", -1), history[0].get("frame", -1) + expected_frames)):
        raise ValueError("original frame sequence has a gap")
    held = []
    for row in history:
        _require_source(row.get("source"), "original frame")
        if row.get("phase") != "parked_hold":
            continue
        ego = _polygon(row.get("ego_body_polygon_m"), "ego body")
        others = [_polygon(body, "other body") for body in row.get("other_body_polygons_m", [])]
        widths = [continuous_free_width_m(section["left_xy_m"], section["right_xy_m"],
                                          [ego, *others]) * FEET_PER_M for section in sections]
        held.append({"frame": row["frame"], "minimum_continuous_width_ft": round(min(widths), 6),
                     "section_widths_ft": [round(width, 6) for width in widths],
                     "other_vehicle_count": len(others)})
    if not held:
        raise ValueError("original parked hold absent")
    return {"case_id": case_id, "source_classification": "other_alley",
            "ordinance_status": geometry["ordinance_status"],
            "minimum_available_continuous_width_ft": min(r["minimum_continuous_width_ft"] for r in held),
            "statutory_less_than_10_ft_observed": min(r["minimum_continuous_width_ft"] for r in held) < 10.0,
            "held_samples": held, "free_vehicular_movement_judgment": "unresolved",
            "ordinance_applicability_judgment": "unresolved",
            "source_sha256": hashlib.sha256(json.dumps(geometry,sort_keys=True).encode()).hexdigest()}


def measure_saved(attempt, case_id, *, expected_frames=900):
    """Reopen sealed original packet bytes; reject missing or changed sources."""
    root = Path(attempt)
    inventory = json.loads((root / "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original alley-width inventory identity missing")
    packets = {}
    for name in ("alley_geometry", "width_history", "frame_map"):
        ref = inventory.get("sources", {}).get(name)
        if not isinstance(ref, dict) or ref.get("path") != name + ".json":
            raise ValueError("original " + name + " packet missing")
        raw = (root / ref["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref.get("sha256"):
            raise ValueError("original " + name + " packet hash changed")
        packets[name] = json.loads(raw)
    joined = packets["frame_map"].get("frames")
    history = packets["width_history"].get("samples")
    if not isinstance(joined, list) or not isinstance(history, list) or len(joined) != expected_frames:
        raise ValueError("original width frame map incomplete")
    if [(r.get("frame"), r.get("time_s")) for r in joined] != [
            (r.get("frame"), r.get("time_s")) for r in history]:
        raise ValueError("original width history/frame time join differs")
    return measure(case_id, packets["alley_geometry"], history,
                   expected_frames=expected_frames)
