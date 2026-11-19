"""CARLA-lazy connected turn geometry for the assigned C147331 lane cell.

This selects route intent and observable lane geometry. It cannot establish
whether a later movement is lawful or physically realized.
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


def select_marked_one_way_turn(carla_map, *, spacing_m=2.0, approach_steps=15,
                               candidate_index=0):
    """Choose a marked one-way pair with a connected left turn from its left lane.

    Ego starts in the right lane and crosses toward the left lane before the
    junction. Same-sign lane IDs are only a map engineering screen for direction.
    """
    if not (isfinite(spacing_m) and spacing_m > 0) or approach_steps < 4:
        raise ValueError("Invalid turn route sampling")
    waypoints = list(carla_map.generate_waypoints(spacing_m))
    signs = {}
    for wp in waypoints:
        if _driving(wp) and int(wp.lane_id) != 0:
            signs.setdefault(int(wp.road_id), set()).add(1 if wp.lane_id > 0 else -1)
    candidates = []
    for start in waypoints:
        if (not _driving(start) or start.is_junction or not _marked(start)
                or int(start.lane_id) == 0 or len(signs.get(int(start.road_id), ())) != 1):
            continue
        left = start.get_left_lane()
        if (not _driving(left) or left.is_junction or not _marked(left)
                or int(left.road_id) != int(start.road_id)
                or int(left.lane_id) * int(start.lane_id) <= 0):
            continue
        primary, adjacent = [start], [left]
        for _ in range(approach_steps):
            next_primary = [wp for wp in primary[-1].next(spacing_m)
                            if _driving(wp) and not wp.is_junction and _marked(wp)
                            and int(wp.road_id) == int(start.road_id)
                            and int(wp.lane_id) == int(start.lane_id)]
            next_adjacent = [wp for wp in adjacent[-1].next(spacing_m)
                             if _driving(wp) and not wp.is_junction and _marked(wp)
                             and int(wp.road_id) == int(left.road_id)
                             and int(wp.lane_id) == int(left.lane_id)]
            if len(next_primary) != 1 or len(next_adjacent) != 1:
                break
            primary.append(next_primary[0])
            adjacent.append(next_adjacent[0])
        if len(primary) != approach_steps + 1:
            continue
        for junction in adjacent[-1].next(spacing_m):
            if not _driving(junction) or not junction.is_junction:
                continue
            for exit_wp in junction.next(8.0):
                if not _driving(exit_wp) or exit_wp.is_junction or not _marked(exit_wp):
                    continue
                angle = _left_angle(adjacent[-1], exit_wp)
                if 45 <= angle <= 135:
                    candidates.append((int(start.road_id), abs(int(start.lane_id)),
                                       int(start.lane_id), float(start.transform.location.x),
                                       float(start.transform.location.y), primary, adjacent,
                                       junction, exit_wp, angle))
    candidates.sort(key=lambda row: row[:5])
    if not candidates:
        raise ValueError("No connected marked one-way multilane turn route found")
    if type(candidate_index) is not int or candidate_index < 0 or candidate_index >= len(candidates):
        raise ValueError("Requested turn route candidate is unavailable")
    row = candidates[candidate_index]
    primary, adjacent, junction, exit_wp, angle = row[5:]
    return {"primary": primary, "adjacent": adjacent, "junction": junction,
            "exit": exit_wp, "road_id": row[0],
            "lane_id": int(primary[0].lane_id),
            "adjacent_lane_id": int(adjacent[0].lane_id),
            "exit_road_id": int(exit_wp.road_id),
            "requested_heading_change_deg": angle}
