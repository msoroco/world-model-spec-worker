"""Connected same-lane Native route for a 300-foot following probe."""

from math import atan2, hypot


def select_follow_route(world_map, *, target_gap_ft=299, step_m=2.5,
                        extra_steps=12):
    if target_gap_ft <= 0 or step_m <= 0:
        raise ValueError('Following route distance invalid')
    lead_index = round((target_gap_ft * .3048 + 4.5) / step_m)
    required_steps = lead_index + extra_steps
    for transform in world_map.get_spawn_points():
        start = world_map.get_waypoint(transform.location)
        if start is None or start.is_junction:
            continue
        chain = [start]
        for _ in range(required_steps):
            options = [candidate for candidate in chain[-1].next(step_m)
                       if candidate.road_id == start.road_id and
                       candidate.lane_id == start.lane_id and
                       not candidate.is_junction]
            if len(options) != 1:
                break
            chain.append(options[0])
        if len(chain) == required_steps + 1:
            return {'ego': chain[0], 'lead': chain[lead_index],
                    'chain': chain, 'requested_gap_ft': target_gap_ft,
                    'lead_index': lead_index}
    raise ValueError('No connected same-lane route for 300-foot following probe')


def cruise_control(position_xy, heading_xy, velocity_xy, target_xy,
                   *, target_speed_mps=6):
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    if hypot(dx, dy) < .2:
        raise ValueError('Following route target collapsed')
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError('Following subject heading undefined')
    angle = atan2((hx * dy - hy * dx) / norm,
                  (hx * dx + hy * dy) / norm)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.5, min(.5, .8 * angle)),
            'throttle': max(0., min(.5, .22 * (target_speed_mps - speed))),
            'brake': max(0., min(.5, .2 * (speed - target_speed_mps)))}
