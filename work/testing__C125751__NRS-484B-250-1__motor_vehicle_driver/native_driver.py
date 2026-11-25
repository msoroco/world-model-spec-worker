"""Lazy CARLA actuator requests for the reviewed C125751 crossing.

Requests are engineering inputs; the saved original body and signal history
remains the only measurement source.
"""
from __future__ import annotations

import math

from saved_signal_audit import _body_overlaps
from signal_crossing import controller_request


def body_polygon(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError('Native vehicle body lacks eight vertices')
    points = [(float(v.x), float(v.y)) for v in vertices]
    if any(not math.isfinite(v) for point in points for v in point):
        raise ValueError('Native body vertex is nonfinite')
    unique = set(points)
    if len(unique) != 4:
        raise ValueError('Native body projection lacks four corners')
    center = (sum(x for x, _ in unique) / 4, sum(y for _, y in unique) / 4)
    return [list(point) for point in sorted(unique,
            key=lambda p: math.atan2(p[1] - center[1], p[0] - center[0]))]


def control_step(spec, packet, state, *, frame, ego_body, other_body,
                 light_readback):
    if type(frame) is not int or frame <= state.get('last_frame', -1):
        raise ValueError('stale original control frame')
    if 'last_frame' in state and frame != state['last_frame'] + 1:
        raise ValueError('gap in original control frames')
    bounds = packet['crossing_bounds_xy_m']
    ego_inside = _body_overlaps(ego_body, bounds)
    other_inside = _body_overlaps(other_body, bounds)
    if state.get('other_cleared') and other_inside:
        raise ValueError('other reentered crossing after clearance')
    other_entered = state.get('other_entered', False) or other_inside
    route = packet['other_route_xy_m']
    delta = [route[-1][i] - route[0][i] for i in (0, 1)]
    axis = 0 if abs(delta[0]) > abs(delta[1]) else 1
    if delta[axis] == 0:
        raise ValueError('other route has no exit direction')
    beyond_exit = (min(v[axis] for v in other_body) > bounds[axis + 2]
                   if delta[axis] > 0 else
                   max(v[axis] for v in other_body) < bounds[axis])
    other_cleared = state.get('other_cleared', False) or (
        state.get('other_entered', False) and not other_inside and beyond_exit)
    ego_entered = state.get('ego_entered', False) or ego_inside
    request = controller_request(
        ego_before=not ego_entered, other_entered=other_entered,
        other_cleared=other_cleared, light_readback=light_readback,
        fresh=True,
        require_other_first=spec['other_first'] and
        spec['ego_response_request'] == 'yield')
    return {'last_frame': frame, 'other_entered': other_entered,
            'other_cleared': other_cleared, 'ego_entered': ego_entered,
            'request': request, 'source': 'same original frame body and signal readback'}


def apply_ego(actor, carla, request):
    if request not in ('brake', 'proceed'):
        raise ValueError('unknown ego request')
    hold = request == 'brake'
    actor.apply_control(carla.VehicleControl(throttle=0 if hold else .25,
                                             brake=1 if hold else 0,
                                             steer=0))


def apply_other(actor, carla, route, *, release, target_index=1):
    if not release:
        actor.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0))
        return target_index
    pose = actor.get_transform()
    x, y = pose.location.x, pose.location.y
    while target_index < len(route) - 1 and math.hypot(
            route[target_index][0] - x, route[target_index][1] - y) < 2:
        target_index += 1
    tx, ty = route[target_index]
    desired = math.atan2(ty - y, tx - x)
    current = math.radians(pose.rotation.yaw)
    error = (desired - current + math.pi) % (2 * math.pi) - math.pi
    steer = max(-.65, min(.65, error * 1.2))
    distance = math.hypot(route[-1][0] - x, route[-1][1] - y)
    velocity = actor.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    arrived = distance < 1
    actor.apply_control(carla.VehicleControl(
        throttle=0 if arrived else max(.08, min(.38, .35 - .08 * speed)),
        brake=1 if arrived else 0, steer=steer))
    return target_index
