"""Native narrow-road route and exposed-person placement for a first-case probe.

The lane-width cap is an engineering scene selector, not a legal definition of
endangerment or sufficient roadway width.
"""

from math import hypot


def select_route(world_map, *, step_m=2.5, steps=16, maximum_lane_width_m=3.25):
    for transform in world_map.get_spawn_points():
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction or not (0 < start.lane_width <= maximum_lane_width_m):
            continue
        route = [start]
        for _ in range(steps):
            options = [item for item in route[-1].next(step_m)
                       if item.road_id == start.road_id and
                       item.lane_id == start.lane_id and
                       not item.is_junction and
                       0 < item.lane_width <= maximum_lane_width_m]
            if len(options) != 1:
                break
            route.append(options[0])
        if len(route) == steps + 1:
            return route
    raise ValueError('No connected narrow-road route for exposure probe')


def exposed_position(route, *, waypoint_index=8, outside_edge_m=0.4):
    if len(route) <= waypoint_index:
        raise ValueError('Narrow-road route lacks participant placement distance')
    waypoint = route[waypoint_index]
    forward = waypoint.transform.get_forward_vector()
    norm = hypot(forward.x, forward.y)
    if norm < 1e-6:
        raise ValueError('Narrow-road tangent undefined')
    # Right-of-travel verge; the case remains measured, not assumed dangerous.
    right = forward.y / norm, -forward.x / norm
    point = waypoint.transform.location
    offset = waypoint.lane_width / 2 + outside_edge_m
    return [point.x + right[0] * offset, point.y + right[1] * offset, point.z]


def speed_control(position_xy, heading_xy, velocity_xy, target_xy, target_speed_mps):
    from math import atan2

    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    if hypot(dx, dy) < 0.2:
        raise ValueError('Exposure target collapsed')
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError('Exposure subject heading undefined')
    error = atan2((hx * dy - hy * dx) / norm,
                  (hx * dx + hy * dy) / norm)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.5, min(.5, .8 * error)),
            'throttle': max(0., min(.45, .2 * (target_speed_mps - speed))),
            'brake': max(0., min(.5, .2 * (speed - target_speed_mps)))}
