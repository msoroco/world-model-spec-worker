"""Measure original vehicle corners against surveyed turn geometry.

Distances describe source geometry.  They do not decide what is nearest or
as close as practicable under NRS 484B.400(3).
"""

from math import hypot, isfinite


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Expected original two-dimensional point")
    result = tuple(float(v) for v in value)
    if not all(isfinite(v) for v in result):
        raise ValueError("Nonfinite original point")
    return result


def directed_line(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Expected surveyed directed line")
    start, end = map(point, value)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    if length <= 0:
        raise ValueError("Degenerate surveyed line")
    return start, (dx / length, dy / length), length


def signed_offset(p, origin, direction):
    return direction[0] * (p[1] - origin[1]) - direction[1] * (p[0] - origin[0])


def distance_to_segment(p, origin, direction, length):
    along = (p[0] - origin[0]) * direction[0] + (p[1] - origin[1]) * direction[1]
    along = max(0, min(length, along))
    return hypot(p[0] - origin[0] - along * direction[0],
                 p[1] - origin[1] - along * direction[1])


def measure_frame(body, survey):
    """Preserve per-corner measurements and the original frame identity."""
    phase = body.get("phase")
    if phase not in ("approach", "entry", "departure"):
        raise ValueError("Original body phase is unknown")
    frame = body.get("frame")
    if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
        raise ValueError("Original body frame is invalid")
    corners = [point(v) for v in body.get("body_corners_xy_m", [])]
    if len(corners) != 4 or len(set(corners)) != 4:
        raise ValueError("Need four distinct original body corners")
    center, center_direction, center_length = directed_line(survey["approach_centerline_xy_m"])
    curb, curb_direction, curb_length = directed_line(survey["destination_left_curb_xy_m"])
    center_offsets = [signed_offset(v, center, center_direction) for v in corners]
    curb_distances = [distance_to_segment(v, curb, curb_direction, curb_length) for v in corners]
    return {
        "frame": frame,
        "phase": phase,
        "approach_centerline_signed_corner_offsets_m": center_offsets,
        "all_corners_right_of_approach_centerline": max(center_offsets) < 0,
        "departure_left_curb_corner_distances_m": curb_distances,
        "farthest_body_corner_from_departure_left_curb_m": max(curb_distances),
    }
