"""CARLA-lazy alley route selection and subject feedback control.

The polygon and its source must be supplied by a future exact construction.
Neither an alley label nor a speed command establishes physical endangerment.
"""

from math import atan2, hypot

from shapely.geometry import Point as ShapelyPoint, Polygon


def select_alley_route(world_map, polygon_xy, *, direction, polygon_source,
                       minimum_steps=12, step_m=2.5, vehicle_width_m=1.8,
                       edge_margin_m=0.25):
    if direction not in ('east', 'west'):
        raise ValueError('Alley route requires east or west direction')
    if not polygon_source or not isinstance(polygon_source, str):
        raise ValueError('Alley polygon needs an original source reference')
    polygon = Polygon(polygon_xy)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Authored alley polygon is invalid')
    safe = polygon.buffer(-vehicle_width_m/2-edge_margin_m)
    if safe.is_empty or minimum_steps < 2 or step_m <= 0:
        raise ValueError('Alley geometry cannot contain the subject route')
    sign = 1 if direction == 'east' else -1

    def inside(waypoint):
        location = waypoint.transform.location
        return safe.covers(ShapelyPoint(location.x, location.y))

    for transform in world_map.get_spawn_points():
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction or not inside(start):
            continue
        forward = start.transform.get_forward_vector()
        if forward.x * sign < .8 or start.lane_width < vehicle_width_m + 2*edge_margin_m:
            continue
        route = [start]
        while len(route) <= minimum_steps:
            options = [candidate for candidate in route[-1].next(step_m)
                       if candidate.road_id == start.road_id and
                       candidate.lane_id == start.lane_id and
                       not candidate.is_junction and inside(candidate)]
            if len(options) != 1:
                break
            route.append(options[0])
        if len(route) == minimum_steps + 1:
            return route
    raise ValueError('No connected mapped route inside sourced alley polygon')


def control_step(position_xy, forward_xy, velocity_xy, target_xy, *, target_speed_mps):
    if target_speed_mps <= 0:
        raise ValueError('Alley target speed must be positive')
    dx, dy = target_xy[0]-position_xy[0], target_xy[1]-position_xy[1]
    if hypot(dx, dy) < .2:
        raise ValueError('Alley route target too close')
    fx, fy = forward_xy
    norm = hypot(fx, fy)
    if norm < 1e-6:
        raise ValueError('Alley subject heading undefined')
    fx, fy = fx/norm, fy/norm
    error = atan2(fx*dy-fy*dx, fx*dx+fy*dy)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.55, min(.55, .8*error)),
            'throttle': max(0., min(.5, .2*(target_speed_mps-speed))),
            'brake': max(0., min(.5, .2*(speed-target_speed_mps)))}
