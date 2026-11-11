"""CARLA-lazy lane selection and route targets for exact C147331 cases.

The selected route has two same-direction adjacent driving lanes, observed
markings and no junction waypoint. A Native run must verify physical coverage.
"""

from __future__ import annotations

from math import atan2, hypot, isfinite, pi


CASE_SUFFIXES = ("within_marked_lane", "unexcused_boundary_crossing",
                 "passing_boundary_crossing")


def _xy(location):
    result = (float(location.x), float(location.y))
    if not all(isfinite(value) for value in result):
        raise ValueError("Nonfinite Native waypoint")
    return result


def _marked(waypoint):
    left = getattr(waypoint, "left_lane_marking", None)
    right = getattr(waypoint, "right_lane_marking", None)
    return all(marking is not None and
               str(marking.type).rsplit(".", 1)[-1].lower() != "none"
               for marking in (left, right))


def _driving(waypoint):
    return waypoint is not None and "driving" in str(waypoint.lane_type).lower()


def _same_lane(a, b):
    return (b is not None and int(b.road_id) == int(a.road_id)
            and int(b.lane_id) == int(a.lane_id))


def _chain(start, steps, spacing_m):
    chain = [start]
    current = start
    for _ in range(steps):
        options = [nxt for nxt in current.next(spacing_m) if _same_lane(current, nxt)]
        if len(options) != 1:
            raise ValueError("Selected Native lane has no unique connected continuation")
        current = options[0]
        if current.is_junction or not _marked(current):
            raise ValueError("Selected Native lane loses markings or enters junction")
        chain.append(current)
    return chain


def select_marked_one_way_pair(carla_map, *, spacing_m=2.0, steps=15,
                               candidate_index=0):
    """Select a deterministic marked straight route with same-direction pair.

    Road-level absence of opposite-sign driving lane IDs is an engineering
    one-way screen, not a claim about jurisdiction or all connected segments.
    """
    waypoints = list(carla_map.generate_waypoints(spacing_m))
    road_signs = {}
    for wp in waypoints:
        if _driving(wp):
            road_signs.setdefault(int(wp.road_id), set()).add(1 if wp.lane_id > 0 else -1)
    candidates = []
    for start in waypoints:
        if not _driving(start) or start.is_junction or not _marked(start):
            continue
        if int(start.lane_id) == 0 or len(road_signs.get(int(start.road_id), ())) != 1:
            continue
        neighbors = [neighbor for neighbor in (start.get_left_lane(), start.get_right_lane())
                     if _driving(neighbor) and int(neighbor.road_id) == int(start.road_id)
                     and int(neighbor.lane_id) * int(start.lane_id) > 0
                     and _marked(neighbor) and not neighbor.is_junction]
        if not neighbors:
            continue
        try:
            primary = _chain(start, steps, spacing_m)
            adjacent = _chain(neighbors[0], steps, spacing_m)
        except ValueError:
            continue
        if any(int(a.road_id) != int(b.road_id) or
               int(a.lane_id) * int(b.lane_id) <= 0
               for a, b in zip(primary, adjacent)):
            continue
        candidates.append((start, primary, adjacent))
    if not candidates:
        raise ValueError("No connected marked one-way multilane route found")
    candidates.sort(key=lambda item: (int(item[0].road_id), abs(int(item[0].lane_id)),
                                      int(item[0].lane_id),
                                      *_xy(item[0].transform.location)))
    if type(candidate_index) is not int or candidate_index < 0 or candidate_index >= len(candidates):
        raise ValueError("Requested marked route candidate is unavailable")
    start, primary, adjacent = candidates[candidate_index]
    return {"road_id": int(start.road_id), "lane_id": int(start.lane_id),
            "adjacent_lane_id": int(adjacent[0].lane_id),
            "primary": primary, "adjacent": adjacent}


def route_targets(selection, case_suffix, *, crossing_fraction=0.6):
    """Compute route-relative body-center targets and optional passing spawn.

    The fraction is an engineering path request; saved body-footprint evidence
    decides whether crossing actually occurred. It is not a legal threshold.
    """
    if case_suffix not in CASE_SUFFIXES:
        raise ValueError("Unknown exact lane case")
    if not (isfinite(crossing_fraction) and 0 < crossing_fraction < 1):
        raise ValueError("Invalid crossing construction fraction")
    primary = selection["primary"]
    adjacent = selection["adjacent"]
    if len(primary) != len(adjacent) or len(primary) < 4:
        raise ValueError("Matched adjacent Native route samples required")
    route = []
    for index, (base, neighbor) in enumerate(zip(primary, adjacent)):
        a, b = _xy(base.transform.location), _xy(neighbor.transform.location)
        if hypot(a[0] - b[0], a[1] - b[1]) <= 0:
            raise ValueError("Adjacent Native lane centers coincide")
        fraction = 0.0 if case_suffix == "within_marked_lane" else (
            crossing_fraction if index >= len(primary) // 2 else 0.0)
        route.append([a[0] + fraction * (b[0] - a[0]),
                      a[1] + fraction * (b[1] - a[1])])
    return {"case_suffix": case_suffix, "targets_xy_m": route,
            "overtaken_spawn": primary[len(primary) // 2].transform
            if case_suffix == "passing_boundary_crossing" else None,
            "engineering_crossing_fraction": 0.0 if case_suffix == "within_marked_lane"
            else crossing_fraction}


def control_step(position_xy, forward_xy, velocity_xy_mps, target_xy,
                 *, target_speed_mps=6.0, heading_gain=1.4, speed_gain=0.25):
    """Return bounded throttle/brake/steer requests from Native readbacks.

    The same controller parameters apply to every linked exact case. Requested
    speed is an engineering construction value, not a legal speed threshold.
    """
    points = [tuple(float(value) for value in pair)
              for pair in (position_xy, forward_xy, velocity_xy_mps, target_xy)]
    if any(len(pair) != 2 or not all(isfinite(value) for value in pair)
           for pair in points):
        raise ValueError("Invalid Native controller readback")
    position, forward, velocity, target = points
    if not (isfinite(target_speed_mps) and target_speed_mps > 0 and
            isfinite(heading_gain) and heading_gain > 0 and
            isfinite(speed_gain) and speed_gain > 0):
        raise ValueError("Invalid engineering controller gains")
    bearing = atan2(target[1] - position[1], target[0] - position[0])
    heading = atan2(forward[1], forward[0])
    if hypot(*forward) <= 0 or hypot(target[0] - position[0],
                                     target[1] - position[1]) <= 0:
        raise ValueError("Controller heading or target undefined")
    angle = (bearing - heading + pi) % (2 * pi) - pi
    steer = max(-1.0, min(1.0, heading_gain * angle / (pi / 2)))
    speed = hypot(*velocity)
    speed_error = target_speed_mps - speed
    return {"steer": steer,
            "throttle": max(0.0, min(1.0, speed_gain * speed_error)),
            "brake": max(0.0, min(1.0, -speed_gain * speed_error))}
