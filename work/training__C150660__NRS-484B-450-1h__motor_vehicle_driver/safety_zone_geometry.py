"""Raw-map geometry measurements for NRS 484B.450(1)(h).

Coordinates use a local metre frame with the adjacent curb at y=0, safety
zone near edge at y>0, and zone ends along x. Geometry does not decide whether
the Native map really establishes a safety zone or a stopping exception.
"""

from __future__ import annotations

from math import atan2, hypot, isclose, isfinite

FRAME_COUNT = 600
FRAME_RATE = 20
THIRTY_FEET_M = 9.144


def _point_segment_distance(point, a, b):
    ax, ay = a
    bx, by = b
    px, py = point
    ux, uy = bx - ax, by - ay
    d = ux * ux + uy * uy
    if d == 0:
        raise ValueError("degenerate vehicle footprint")
    t = max(0.0, min(1.0, ((px - ax) * ux + (py - ay) * uy) / d))
    return hypot(px - ax - t * ux, py - ay - t * uy)


def _point_footprint_distance(point, corners):
    px, py = point
    inside = False
    for i, (ax, ay) in enumerate(corners):
        bx, by = corners[(i + 1) % len(corners)]
        if (ay > py) != (by > py) and px < (bx - ax) * (py - ay) / (by - ay) + ax:
            inside = not inside
    if inside:
        return 0.0
    return min(_point_segment_distance(point, corners[i], corners[(i + 1) % len(corners)]) for i in range(len(corners)))


def _ordered_footprint(corners):
    """CARLA corner loops arrive in x-major order, not perimeter order."""
    cx = sum(x for x, _ in corners) / 4
    cy = sum(y for _, y in corners) / 4
    ordered = sorted(corners, key=lambda p: atan2(p[1] - cy, p[0] - cx))
    twice_area = sum(ordered[i][0] * ordered[(i + 1) % 4][1] -
                     ordered[(i + 1) % 4][0] * ordered[i][1] for i in range(4))
    if abs(twice_area) < 1e-8:
        raise ValueError("degenerate vehicle footprint")
    return ordered


def measure_frame(corners: list, zone: dict) -> dict:
    if not zone.get("zone_map_source") or not zone.get("curb_map_source"):
        raise ValueError("safety zone and curb source provenance required")
    try:
        lo, hi = float(zone["x_start_m"]), float(zone["x_end_m"])
        curb, near = float(zone["curb_y_m"]), float(zone["zone_near_y_m"])
        pts = [(float(x), float(y)) for x, y in corners]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid source geometry") from exc
    if len(pts) != 4 or not all(isfinite(v) for p in pts for v in p) or not lo < hi or not curb < near:
        raise ValueError("invalid source geometry")
    if len(set(pts)) != 4:
        raise ValueError("degenerate vehicle footprint")
    pts = _ordered_footprint(pts)
    opposite_start = (lo, curb)
    opposite_end = (hi, curb)
    distances = (_point_footprint_distance(opposite_start, pts), _point_footprint_distance(opposite_end, pts))
    return {
        "fully_between_zone_and_curb": all(lo <= x <= hi and curb <= y <= near for x, y in pts),
        "distance_to_opposite_start_m": distances[0],
        "distance_to_opposite_end_m": distances[1],
        "within_30_feet_of_opposite_end_points": any(
            d <= THIRTY_FEET_M or isclose(d, THIRTY_FEET_M, rel_tol=0, abs_tol=1e-12)
            for d in distances),
        "thirty_feet_m": THIRTY_FEET_M,
        "zone_validity_conclusion": None,
        "exception_conclusion": None,
    }


def measure_trace(rows: list[dict], zone: dict) -> dict:
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    stopped_between = 0
    stopped_near_end = 0
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        if type(row.get("vehicle_stopped")) is not bool or not row.get("stop_state_source"):
            raise ValueError("measured stop-state source required")
        m = measure_frame(row.get("vehicle_footprint_corners_m"), zone)
        stopped_between += int(row["vehicle_stopped"] and m["fully_between_zone_and_curb"])
        stopped_near_end += int(row["vehicle_stopped"] and m["within_30_feet_of_opposite_end_points"])
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "stopped_between_frames": stopped_between,
        "stopped_within_30_feet_of_end_frames": stopped_near_end,
        "legal_conclusion": None,
        "source_kind": "unverified_raw_map_and_actor_fields",
    }


def audit_selected_pair(between_rows: list[dict], outside_rows: list[dict], zone: dict) -> dict:
    """Check that the planned stopped-position pair holds other sources fixed."""
    if len(between_rows) != FRAME_COUNT or len(outside_rows) != FRAME_COUNT:
        raise ValueError("selected pair must contain 600 frames per condition")
    variable = "vehicle_footprint_corners_m"
    for first, second in zip(between_rows, outside_rows):
        if set(first) != set(second):
            raise ValueError("selected pair source channels differ")
        if {key: value for key, value in first.items() if key != variable} != {key: value for key, value in second.items() if key != variable}:
            raise ValueError("selected pair changed fixed stop-state or timing source")
    between = measure_trace(between_rows, zone)
    outside = measure_trace(outside_rows, zone)
    if between["stopped_between_frames"] < 1 or outside["stopped_between_frames"] != 0 or outside["stopped_within_30_feet_of_end_frames"] != 0:
        raise ValueError("selected pair lacks isolated safety-zone position change")
    return {"between": between, "outside": outside,
            "comparison_variable": "stopped_vehicle_position_relative_to_safety_zone",
            "isolation_checked": True, "physical_zone_confirmed": False}
