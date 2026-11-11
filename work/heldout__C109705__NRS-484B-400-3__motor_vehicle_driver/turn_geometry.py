"""Measured geometry for the two-directional-to-one-way left-turn branch.

Inputs are original surveyed line segments and measured Native body corners.
Signed positions and distances are descriptive, not statutory cutoffs.
"""

from math import hypot, isfinite


def _point(value):
    if len(value) != 2:
        raise ValueError("Expected two-dimensional point")
    result = tuple(float(v) for v in value)
    if not all(isfinite(v) for v in result):
        raise ValueError("Nonfinite surveyed geometry")
    return result


def _line(segment):
    if len(segment) != 2:
        raise ValueError("Expected surveyed line segment")
    a, b = (_point(value) for value in segment)
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = hypot(dx, dy)
    if length <= 0:
        raise ValueError("Degenerate surveyed line")
    return a, b, (dx / length, dy / length), length


def _signed_lateral(point, a, forward):
    return forward[0] * (point[1] - a[1]) - forward[1] * (point[0] - a[0])


def _distance_to_segment(point, a, b, forward, length):
    along = (point[0] - a[0]) * forward[0] + (point[1] - a[1]) * forward[1]
    clamped = max(0, min(length, along))
    return hypot(point[0] - a[0] - clamped * forward[0],
                 point[1] - a[1] - clamped * forward[1])


def measure_turn_position(body_corners, *, approach_centerline,
                          destination_left_curb, intersection_entry):
    """Preserve all corner offsets to the approach centerline and left curb.

    Approach segment points toward the intersection. Negative signed lateral
    values are on its right. Destination curb points in the one-way travel
    direction, so positive signed lateral values lie left of its directed line.
    Callers must source and verify roadway direction and line identity.
    """
    corners = [_point(value) for value in body_corners]
    if len(corners) != 4 or len(set(corners)) != 4:
        raise ValueError("Need four distinct measured body corners")
    entry = _point(intersection_entry)
    ca, cb, cf, clen = _line(approach_centerline)
    ka, kb, kf, klen = _line(destination_left_curb)
    if _distance_to_segment(entry, ca, cb, cf, clen) > 1e-6:
        raise ValueError("Intersection entry is not on surveyed centerline")
    return {
        "approach_signed_corner_offsets_m": [_signed_lateral(p, ca, cf) for p in corners],
        "approach_all_corners_right_of_centerline": all(
            _signed_lateral(p, ca, cf) < 0 for p in corners),
        "destination_curb_signed_corner_offsets_m": [_signed_lateral(p, ka, kf)
                                                      for p in corners],
        "destination_curb_corner_distances_m": [_distance_to_segment(p, ka, kb, kf, klen)
                                                for p in corners],
        "intersection_entry_xy_m": list(entry),
    }
