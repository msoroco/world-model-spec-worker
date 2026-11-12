"""Bounded Native route follower for measured one-way left-turn sweeps.

The lateral targets are engineering requests. Retained body footprints decide
what each actor actually did; they are never replaced by controller targets.
"""
from math import atan2, cos, hypot, radians, sin


def _point(wp):
    location = wp.transform.location
    return (float(location.x), float(location.y))


def target_route_points(survey, case, *, lateral_scale=1.0):
    route = survey['connected_route']
    if len(route) < 3:
        raise ValueError('connected turn route too short')
    approach_road = int(survey['approach'].road_id)
    departure_road = int(survey['departure'].road_id)
    approach_shift = case.approach_center_x - (-4.5)
    departure_shift = case.departure_center_y - (-4.5)
    if not 0 <= approach_shift <= 1 or not 0 <= departure_shift <= 1:
        raise ValueError('case lateral sweep outside authored physical span')
    if not .5 <= lateral_scale <= 1.2:
        raise ValueError('lateral engineering scale outside bound')
    result = []
    for index, wp in enumerate(route):
        road = int(wp.road_id)
        if road == approach_road:
            lateral = approach_shift
        elif road == departure_road:
            lateral = departure_shift
        else:
            # The connected junction is a transition, so blend the two targets.
            lateral = (approach_shift + departure_shift)/2
        yaw = radians(float(wp.transform.rotation.yaw))
        x, y = _point(wp)
        right = (sin(yaw), -cos(yaw))
        result.append((x + lateral_scale*lateral*right[0],
                       y + lateral_scale*lateral*right[1]))
    return result


def command(actor, carla, points, *, target_mps=5.0, speed_kp=.22, lookahead_m=3.0):
    if actor is None or not actor.is_alive:
        raise ValueError('turning actor absent')
    if len(points) < 3 or not 0 < target_mps <= 12 or not 0 < speed_kp <= .5:
        raise ValueError('invalid route controller request')
    transform = actor.get_transform()
    x, y = float(transform.location.x), float(transform.location.y)
    nearest = min(range(len(points)), key=lambda i: hypot(points[i][0]-x,points[i][1]-y))
    index = nearest
    while index < len(points)-1 and hypot(points[index][0]-x,points[index][1]-y) < lookahead_m:
        index += 1
    tx, ty = points[index]
    heading = atan2(ty-y,tx-x)
    yaw = radians(float(transform.rotation.yaw))
    error = atan2(sin(heading-yaw),cos(heading-yaw))
    velocity = actor.get_velocity()
    speed = hypot(float(velocity.x),float(velocity.y))
    speed_error = target_mps-speed
    applied = carla.VehicleControl(
        throttle=min(.65,max(0.,speed_kp*speed_error)),
        brake=min(.8,max(0.,-.3*speed_error)),
        steer=min(.5,max(-.5,error/.7)))
    actor.apply_control(applied)
    return {'route_index': index, 'requested_target_mps': target_mps,
            'requested_steer': applied.steer,
            'requested_throttle': applied.throttle,
            'requested_brake': applied.brake}
