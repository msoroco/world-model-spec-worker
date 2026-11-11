"""Select a connected roadway approach and left turn; feedback steer a bicycle."""

from math import atan2, cos, hypot, radians, sin


def _yaw_delta(first, last):
    angle = radians(last - first)
    return atan2(sin(angle), cos(angle)) * 180 / 3.141592653589793


def select_left_turn(world_map, *, step_m=2.5):
    for spawn in world_map.get_spawn_points():
        start = world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        approach = [start]
        for _ in range(8):
            options = [w for w in approach[-1].next(step_m)
                       if w.road_id == start.road_id and
                       w.lane_id == start.lane_id]
            if len(options) != 1:
                break
            approach.append(options[0])
        if len(approach) != 9:
            continue
        frontier = [(approach[-1], [])]
        for _ in range(16):
            next_frontier = []
            for waypoint, path in frontier:
                for nxt in waypoint.next(step_m):
                    if any(nxt is old for old in path):
                        continue
                    expanded = path + [nxt]
                    delta = _yaw_delta(start.transform.rotation.yaw,
                                       nxt.transform.rotation.yaw)
                    if 65 <= delta <= 130 and len(expanded) >= 6:
                        return approach + expanded
                    if len(next_frontier) < 32:
                        next_frontier.append((nxt, expanded))
            frontier = next_frontier
            if not frontier:
                break
    raise ValueError('No connected Native roadway left-turn route')


def control(position_xy, heading_xy, velocity_xy, target_xy, *, target_speed_mps=3):
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    distance = hypot(dx, dy)
    if distance < .15:
        raise ValueError('Rider route target collapsed')
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError('Rider heading undefined')
    angle = atan2((hx * dy - hy * dx) / norm,
                  (hx * dx + hy * dy) / norm)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.5, min(.5, 1.1 * angle)),
            'throttle': max(0, min(.55, .3 * (target_speed_mps - speed))),
            'brake': max(0, min(.5, .25 * (speed - target_speed_mps)))}
