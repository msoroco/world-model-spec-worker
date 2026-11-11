"""Select an original connected direct-course approach and left turn."""
from math import atan2, hypot, isfinite, pi, degrees


def _xy(waypoint):
    location = waypoint.transform.location
    xy = float(location.x), float(location.y)
    if not all(isfinite(v) for v in xy):
        raise ValueError('Nonfinite Native route waypoint')
    return xy


def _heading(waypoint):
    direction = waypoint.transform.get_forward_vector()
    xy = float(direction.x), float(direction.y)
    if not all(isfinite(v) for v in xy) or hypot(*xy) < .1:
        raise ValueError('Invalid Native route heading')
    return atan2(xy[1], xy[0])


def _driving(waypoint):
    return waypoint is not None and 'driving' in str(waypoint.lane_type).lower()


def select_left_turn(carla_map, *, spacing_m=2., approach_steps=6, candidate_index=0):
    if not (isfinite(spacing_m) and spacing_m > 0 and
            type(approach_steps) is int and approach_steps >= 4 and
            type(candidate_index) is int and candidate_index >= 0):
        raise ValueError('Invalid connected-turn route sampling')
    candidates = []
    for start in carla_map.generate_waypoints(spacing_m):
        if not _driving(start) or start.is_junction:
            continue
        approach = [start]
        for _ in range(approach_steps):
            previous = approach[-1]
            next_steps = [item for item in previous.next(spacing_m)
                          if _driving(item) and not item.is_junction and
                          (item.road_id, item.lane_id) == (start.road_id, start.lane_id)]
            if len(next_steps) != 1:
                break
            approach.append(next_steps[0])
        if len(approach) != approach_steps + 1:
            continue
        for junction in approach[-1].next(spacing_m):
            if not _driving(junction) or not junction.is_junction:
                continue
            for exit_wp in junction.next(8.):
                if not _driving(exit_wp) or exit_wp.is_junction:
                    continue
                delta = degrees((_heading(exit_wp) - _heading(approach[-1]) + pi) % (2 * pi) - pi)
                if 45 <= delta <= 135:
                    candidates.append((int(start.road_id), int(start.lane_id), *_xy(start),
                                       {'approach': approach, 'junction': junction,
                                        'exit': exit_wp, 'heading_change_deg': delta}))
    candidates.sort(key=lambda item: item[:4])
    if candidate_index >= len(candidates):
        raise ValueError('No connected left-turn route at requested sampling')
    return candidates[candidate_index][-1]


def route_targets(scene):
    return [list(_xy(waypoint)) for waypoint in
            (*scene['approach'], scene['junction'], scene['exit'])]


def control_step(position_xy, forward_xy, velocity_xy, target_xy,
                 *, target_speed_mps=5., heading_gain=1.4, speed_gain=.25):
    points = [tuple(float(value) for value in pair)
              for pair in (position_xy, forward_xy, velocity_xy, target_xy)]
    if any(len(pair) != 2 or not all(isfinite(v) for v in pair) for pair in points):
        raise ValueError('Invalid Native turn controller readback')
    if not (isfinite(target_speed_mps) and target_speed_mps > 0 and
            isfinite(heading_gain) and heading_gain > 0 and
            isfinite(speed_gain) and speed_gain > 0):
        raise ValueError('Invalid turn engineering gain')
    position, forward, velocity, target = points
    if hypot(*forward) < .1 or hypot(target[0]-position[0], target[1]-position[1]) < .01:
        raise ValueError('Turn heading or target undefined')
    bearing = atan2(target[1]-position[1], target[0]-position[0])
    heading = atan2(forward[1], forward[0])
    angle = (bearing-heading+pi)%(2*pi)-pi
    steer = max(-1.,min(1.,heading_gain*angle/(pi/2)))
    speed_error = target_speed_mps-hypot(*velocity)
    return {'steer':steer, 'throttle':max(0.,min(1.,speed_gain*speed_error)),
            'brake':max(0.,min(1.,-speed_gain*speed_error))}
