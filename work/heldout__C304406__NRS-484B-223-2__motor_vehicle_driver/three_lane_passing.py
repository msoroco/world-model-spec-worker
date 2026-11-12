"""CPU geometry for a constructed right-lane passing target and center gap.

Distances here are engineering setup parameters, not legal safe-distance findings.
Actual visible highway and complete traffic clearance need Native source review.
"""

from math import hypot


def unit(vector_xy):
    norm = hypot(*vector_xy)
    if norm < 0.8:
        raise ValueError('Passing route tangent unavailable')
    return vector_xy[0] / norm, vector_xy[1] / norm


def projected_distance(origin_xy, forward_xy, point_xy):
    forward = unit(forward_xy)
    dx, dy = point_xy[0] - origin_xy[0], point_xy[1] - origin_xy[1]
    return dx * forward[0] + dy * forward[1], -dx * forward[1] + dy * forward[0]


def passing_target(right_route, *, target_ahead_m=18.0, route_clear_m=65.0):
    """Choose a real waypoint for a slower target and demand corridor length."""
    if target_ahead_m < 8 or route_clear_m <= target_ahead_m + 20:
        raise ValueError('Passing setup needs a separated target and corridor')
    if len(right_route) < 3:
        raise ValueError('Passing route too short')
    origin = right_route[0].transform.location
    tangent = right_route[0].transform.get_forward_vector()
    vector = (tangent.x, tangent.y)
    positions = []
    for waypoint in right_route:
        point = waypoint.transform.location
        along, across = projected_distance((origin.x, origin.y), vector, (point.x, point.y))
        if abs(across) > 0.5:
            raise ValueError('Passing corridor is not straight enough')
        positions.append(along)
    if any(b <= a for a, b in zip(positions, positions[1:])) or positions[-1] < route_clear_m:
        raise ValueError('Passing corridor lacks clear route length')
    index = min(range(1, len(right_route)), key=lambda i: abs(positions[i] - target_ahead_m))
    if abs(positions[index] - target_ahead_m) > 2:
        raise ValueError('Passing target waypoint spacing too coarse')
    return right_route[index]


def center_clearance(ego_xy, forward_xy, center_xy, actors, *, clear_m=60.0,
                     lane_half_width_m=1.75):
    """Measure actor body intrusion into an engineering center-lane interval."""
    if clear_m <= 0 or lane_half_width_m <= 0:
        raise ValueError('Passing clearance parameters invalid')
    ego_along, ego_across = projected_distance(ego_xy, forward_xy, center_xy)
    if abs(ego_along) > 1 or abs(ego_across) < 2:
        raise ValueError('Center-lane reference differs from subject lane')
    blocked = []
    for actor in actors:
        along, across = projected_distance(center_xy, forward_xy, actor['center_xy'])
        half_length = float(actor['half_length_m'])
        half_width = float(actor['half_width_m'])
        if half_length <= 0 or half_width <= 0:
            raise ValueError('Passing actor body extent invalid')
        if along + half_length >= 0 and along - half_length <= clear_m and abs(across) <= lane_half_width_m + half_width:
            blocked.append({'actor_id': actor['actor_id'], 'nearest_m': max(0.0, along - half_length)})
    return {'clear_target_m': clear_m, 'blocked_actors': blocked,
            'engineering_interval_clear': not blocked,
            'legal_safe_distance': None, 'highway_clearly_visible': None}
