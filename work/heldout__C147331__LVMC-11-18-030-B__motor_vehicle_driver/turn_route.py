"""CARLA-lazy candidate geometry for proposed unallocated C5191 turn branch.

This is a construction primitive, not an allocated delivery construction.
It selects an actually connected marked approach and leftward exit waypoint;
saved original sources would still need to establish any turn exception.
"""

from __future__ import annotations

from math import atan2, degrees, isfinite, pi


def _heading(waypoint):
    vector = waypoint.transform.get_forward_vector()
    x, y = float(vector.x), float(vector.y)
    if not (isfinite(x) and isfinite(y)) or x * x + y * y < 0.01:
        raise ValueError("Invalid Native turn waypoint heading")
    return atan2(y, x)


def _left_angle(start, end):
    return degrees((_heading(end) - _heading(start) + pi) % (2 * pi) - pi)


def _marked(waypoint):
    return all(marking is not None and
               str(marking.type).rsplit(".", 1)[-1].lower() != "none"
               for marking in (getattr(waypoint, "left_lane_marking", None),
                               getattr(waypoint, "right_lane_marking", None)))


def _driving(waypoint):
    return waypoint is not None and "driving" in str(waypoint.lane_type).lower()


def select_marked_left_turn(carla_map, *, spacing_m=2.0, approach_steps=4):
    """Return a reproducible connected left-turn candidate or an explicit gap."""
    if not (isfinite(spacing_m) and spacing_m > 0) or approach_steps < 2:
        raise ValueError("Invalid proposed turn sampling")
    candidates = []
    for start in carla_map.generate_waypoints(spacing_m):
        if not _driving(start) or start.is_junction or not _marked(start):
            continue
        approach = [start]
        current = start
        for _ in range(approach_steps):
            forward = [next_wp for next_wp in current.next(spacing_m)
                       if _driving(next_wp) and next_wp.road_id == current.road_id
                       and next_wp.lane_id == current.lane_id]
            if len(forward) != 1 or forward[0].is_junction or not _marked(forward[0]):
                break
            current = forward[0]
            approach.append(current)
        if len(approach) != approach_steps + 1:
            continue
        junctions = [next_wp for next_wp in current.next(spacing_m)
                     if _driving(next_wp) and next_wp.is_junction]
        for junction in junctions:
            for exit_wp in junction.next(8.0):
                if not _driving(exit_wp) or exit_wp.is_junction or not _marked(exit_wp):
                    continue
                angle = _left_angle(current, exit_wp)
                if 45 <= angle <= 135:
                    candidates.append((int(start.road_id), int(start.lane_id),
                                       float(start.transform.location.x),
                                       float(start.transform.location.y),
                                       approach, junction, exit_wp, angle))
    if not candidates:
        raise ValueError("No connected marked approach and leftward exit found")
    candidates.sort(key=lambda item: item[:4])
    road_id, lane_id, _, _, approach, junction, exit_wp, angle = candidates[0]
    return {"approach": approach, "junction": junction, "exit": exit_wp,
            "approach_road_id": road_id, "approach_lane_id": lane_id,
            "exit_road_id": int(exit_wp.road_id),
            "requested_heading_change_deg": angle}
