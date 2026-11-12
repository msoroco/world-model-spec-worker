"""CARLA-lazy two-way baseline route and body-side controller primitives."""

from math import atan2, hypot

from road_source_capture import _forward, _opposing_neighbor, _xy


def select_two_way_route(world_map, *, steps=16, spacing_m=2.5):
    if type(steps) is not int or steps < 10 or spacing_m <= 0:
        raise ValueError("Invalid two-way baseline route request")
    for spawn in world_map.get_spawn_points():
        start = world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        try:
            _opposing_neighbor(start)
        except ValueError:
            continue
        route = [start]
        for _ in range(steps):
            options = [item for item in route[-1].next(spacing_m)
                       if item.road_id == start.road_id and
                       item.lane_id == start.lane_id and not item.is_junction]
            if len(options) != 1:
                break
            try:
                _opposing_neighbor(options[0])
            except ValueError:
                break
            route.append(options[0])
        if len(route) == steps + 1:
            return route
    raise ValueError("No connected two-way route with opposing centerline")


def baseline_targets(route, *, body_side):
    if body_side not in ("right", "left") or len(route) < 11:
        raise ValueError("Invalid baseline body-side request")
    targets = []
    for waypoint in route:
        center = _xy(waypoint.transform.location)
        opposite = _opposing_neighbor(waypoint)
        if body_side == "right":
            target = center
        else:
            target = _xy(opposite.transform.location)
        targets.append(target)
    if any(hypot(b[0]-a[0], b[1]-a[1]) < 0.25
           for a, b in zip(targets, targets[1:])):
        raise ValueError("Two-way route targets are not distinct")
    return {"targets_xy_m": targets, "body_side": body_side,
            "other_vehicle_start_xy_m": list(_xy(route[8].transform.location)),
            "other_vehicle_role": "same-direction lead vehicle",
            "legal_exception_decided": False}


def control_step(position_xy, heading_xy, velocity_xy, target_xy,
                 *, target_speed_mps=5.0):
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    if hypot(dx, dy) < 0.2:
        raise ValueError("Route target too near for feedback")
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError("Native vehicle heading undefined")
    hx, hy = hx / norm, hy / norm
    error = atan2(hx * dy - hy * dx, hx * dx + hy * dy)
    steer = max(-0.5, min(0.5, 0.8 * error))
    speed = hypot(*velocity_xy)
    throttle = max(0.0, min(0.45, 0.22 * (target_speed_mps - speed)))
    brake = max(0.0, min(0.4, 0.16 * (speed - target_speed_mps)))
    return {"throttle": throttle, "steer": steer, "brake": brake}
