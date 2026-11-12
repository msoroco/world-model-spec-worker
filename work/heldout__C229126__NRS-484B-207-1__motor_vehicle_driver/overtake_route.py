"""Native same-direction two-lane overtaking route and return controller."""

from math import atan2, hypot, isfinite

from overtake_controller import TARGETS


def _heading(waypoint):
    vector = waypoint.transform.get_forward_vector()
    norm = hypot(vector.x, vector.y)
    if norm < 1e-6:
        raise ValueError('Overtake road heading degenerate')
    return vector.x / norm, vector.y / norm


def select_overtake_route(world_map, *, step_m=2.5, steps=70):
    if step_m <= 0 or steps < 20:
        raise ValueError('Overtake route sampling invalid')
    for spawn in world_map.get_spawn_points():
        right = world_map.get_waypoint(spawn.location)
        if right is None or right.is_junction:
            continue
        left = right.get_left_lane()
        if (left is None or left.is_junction or left.road_id != right.road_id or
                _heading(left)[0] * _heading(right)[0] +
                _heading(left)[1] * _heading(right)[1] < .98):
            continue
        right_chain, left_chain = [right], [left]
        for _ in range(steps):
            choices = []
            for chain, first in ((right_chain, right), (left_chain, left)):
                next_same = [candidate for candidate in chain[-1].next(step_m)
                             if candidate.road_id == first.road_id and
                             candidate.lane_id == first.lane_id and
                             not candidate.is_junction]
                choices.append(next_same)
            if any(len(options) != 1 for options in choices):
                break
            right_chain.append(choices[0][0])
            left_chain.append(choices[1][0])
        if len(right_chain) == steps + 1:
            return {'right': right_chain, 'left': left_chain,
                    'road_id': right.road_id,
                    'right_lane_id': right.lane_id,
                    'left_lane_id': left.lane_id}
    raise ValueError('No connected same-direction left-passing lane pair')


def _point(waypoint):
    location = waypoint.transform.location
    return location.x, location.y


def choose_target(route, ego_xy, ego_rear_long_m, other_front_long_m,
                  *, passed_abreast=False, requested_return_clearance_m=3,
                  lookahead=3):
    if (not isfinite(requested_return_clearance_m) or
            not -4 <= requested_return_clearance_m <= 10 or lookahead < 1):
        raise ValueError('Overtake return parameters invalid')
    right = route['right']
    nearest = min(range(len(right)), key=lambda i: hypot(
        ego_xy[0] - _point(right[i])[0], ego_xy[1] - _point(right[i])[1]))
    index = min(nearest + lookahead, len(right) - 1)
    clear = (passed_abreast and
             ego_rear_long_m >= other_front_long_m + requested_return_clearance_m)
    return {'waypoint': (right if clear else route['left'])[index],
            'phase': 'return_right' if clear else 'pass_left',
            'waypoint_index': index,
            'measured_body_clearance_m': ego_rear_long_m - other_front_long_m}


def case_target(route, case_suffix, ego_xy, original_row, *, passed_abreast,
                lookahead=3):
    """Select the exact sweep's lane, signed return point and lateral aim."""
    if case_suffix not in TARGETS:
        raise ValueError('Unknown exact overtaking case')
    left_gap, return_clearance = TARGETS[case_suffix]
    hx, hy = original_row['road_tangent_xy']
    length = hypot(hx, hy)
    if not isfinite(length) or length < .99:
        raise ValueError('Original road tangent invalid')
    ax, ay = hx / length, hy / length
    ego = original_row['ego_corners']
    other = original_row['other_corners']
    if len(ego) != 4 or len(other) != 4:
        raise ValueError('Original four-corner bodies required')
    if any(len(point) != 2 or not all(isfinite(value) for value in point)
           for point in ego + other):
        raise ValueError('Original body coordinates invalid')
    ego_rear = min(x * ax + y * ay for x, y in ego)
    other_front = max(x * ax + y * ay for x, y in other)
    selected = choose_target(route, ego_xy, ego_rear, other_front,
                             passed_abreast=passed_abreast,
                             requested_return_clearance_m=return_clearance,
                             lookahead=lookahead)
    if selected['phase'] == 'return_right':
        selected['target_xy'] = list(_point(selected['waypoint']))
    else:
        lx, ly = -ay, ax
        other_left = max(x * lx + y * ly for x, y in other)
        ego_left = [x * lx + y * ly for x, y in ego]
        ego_center = sum(ego_left) / 4
        desired_center = other_left + max(ego_left) - ego_center + left_gap
        wx, wy = _point(selected['waypoint'])
        offset = desired_center - (wx * lx + wy * ly)
        if abs(offset) > 3:
            raise ValueError('Left pass target outside mapped lane sweep')
        selected['target_xy'] = [wx + offset * lx, wy + offset * ly]
    selected['target_left_gap_m'] = left_gap
    return selected


def steer_speed_control(position_xy, heading_xy, velocity_xy, target_xy,
                        *, target_speed_mps=8):
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    if hypot(dx, dy) < .2:
        raise ValueError('Overtake control target collapsed')
    hx, hy = heading_xy
    norm = hypot(hx, hy)
    if norm < 1e-6:
        raise ValueError('Overtake vehicle heading undefined')
    angle = atan2((hx * dy - hy * dx) / norm,
                  (hx * dx + hy * dy) / norm)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.5, min(.5, .8 * angle)),
            'throttle': max(0., min(.5, .22 * (target_speed_mps - speed))),
            'brake': max(0., min(.5, .2 * (speed - target_speed_mps)))}
