"""Source-aware Native route selection and feedback control for a baseline probe."""

from math import atan2, hypot

from directed_geometry import adjacent_opposing_lane


def select_two_way_route(world_map, *, minimum_steps=12, step_m=2.5):
    """Choose connected mapped right-side travel with an adjacent opposing lane.

    A median-opening witness still needs separate map-specific proof; this selector
    only establishes the two-way geometry needed by the baseline construction.
    """
    for transform in world_map.get_spawn_points():
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        try:
            adjacent_opposing_lane(start)
        except ValueError:
            continue
        route = [start]
        for _ in range(minimum_steps):
            options = route[-1].next(step_m)
            options = [candidate for candidate in options
                       if candidate.road_id == start.road_id and
                       candidate.lane_id == start.lane_id and
                       not candidate.is_junction]
            if not options:
                break
            candidate = options[0]
            try:
                adjacent_opposing_lane(candidate)
            except ValueError:
                break
            route.append(candidate)
        if len(route) == minimum_steps + 1:
            return route
    raise ValueError('No connected two-way baseline route with an original center boundary')


def control_step(position_xy, heading_xy, velocity_xy, target_xy, *, target_speed_mps=5.0):
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    if hypot(dx, dy) < 0.2:
        raise ValueError('Route target too close for stable feedback')
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError('Native actor heading undefined')
    hx, hy = hx / norm, hy / norm
    error = atan2(hx * dy - hy * dx, hx * dx + hy * dy)
    steer = max(-0.55, min(0.55, 0.8 * error))
    speed = hypot(*velocity_xy)
    throttle = max(0.0, min(0.45, 0.22 * (target_speed_mps - speed)))
    brake = max(0.0, min(0.4, 0.16 * (speed - target_speed_mps)))
    return {'throttle': throttle, 'steer': steer, 'brake': brake}
