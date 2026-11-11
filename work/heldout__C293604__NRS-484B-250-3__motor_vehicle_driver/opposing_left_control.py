"""Prospective two-vehicle control for the opposing-left exception scene."""

from math import isfinite

from ending_road_source_capture import _body


def _bounds(points):
    if len(points) < 3 or any(len(point) != 2 or
            not all(isfinite(v) for v in point) for point in points):
        raise ValueError('Opposing-left conflict polygon invalid')
    return min(p[0] for p in points), max(p[0] for p in points), min(p[1] for p in points), max(p[1] for p in points)


def _overlap(body, zone):
    left, right, bottom, top = _bounds(body)
    zl, zr, zb, zt = zone
    return not (right < zl or left > zr or top < zb or bottom > zt)


def turn_release_step(opposite_actor, conflict_polygon_xy, *,
                      opposite_seen_in_zone, turning_released):
    """Hold the turn until the opposite body has entered and fully left the zone.

    The caller retains the booleans across ticks. This controller provides a
    repeatable engineering order, not a legal right-of-way conclusion.
    """
    zone = _bounds(conflict_polygon_xy)
    opposite_overlap = _overlap(_body(opposite_actor), zone)
    seen = opposite_seen_in_zone or opposite_overlap
    released = turning_released or (seen and not opposite_overlap)
    return {'opposite_seen_in_zone': seen,
            'turning_released': released,
            'turning_speed_mps': 4.0 if released else 0.0,
            'opposite_speed_mps': 5.0,
            'opposite_body_overlaps_zone': opposite_overlap}
