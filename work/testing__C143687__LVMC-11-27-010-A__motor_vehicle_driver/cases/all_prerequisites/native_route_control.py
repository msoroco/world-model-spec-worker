"""Source-bound low-speed CARLA route request for an authored trail corridor."""
from __future__ import annotations

import math


def command(vehicle, site, carla, index):
    if type(index) is not int or index < 0:
        raise ValueError('invalid original tick index')
    route = site['route_xy']
    pose = vehicle.get_transform()
    x, y, yaw = float(pose.location.x), float(pose.location.y), float(pose.rotation.yaw)
    velocity = vehicle.get_velocity()
    speed = math.hypot(float(velocity.x), float(velocity.y))
    if not all(math.isfinite(v) for v in (x, y, yaw, speed)):
        raise ValueError('nonfinite original vehicle control readback')
    candidates = route[1:]
    target = next((point for point in candidates if math.hypot(point[0]-x, point[1]-y) > 1.5),
                  route[-1])
    distance = math.hypot(target[0]-x, target[1]-y)
    final_distance = math.hypot(route[-1][0]-x, route[-1][1]-y)
    desired_yaw = math.degrees(math.atan2(target[1]-y, target[0]-x))
    heading_error = ((desired_yaw-yaw+180) % 360)-180
    steer = max(-0.65, min(0.65, heading_error/45))
    target_speed = float(site['target_speed_mps'])
    if final_distance < 1.5:
        throttle, brake = 0.0, 0.75
    elif speed > target_speed + 0.25:
        throttle, brake = 0.0, 0.2
    else:
        throttle, brake = max(0.0, min(0.35, (target_speed-speed)/target_speed*0.35)), 0.0
    control = carla.VehicleControl(throttle=throttle, steer=steer, brake=brake)
    vehicle.apply_control(control)
    return {'tick_index': index, 'position_xy': [x, y], 'speed_mps': speed,
            'target_xy': list(target), 'target_distance_m': distance,
            'final_distance_m': final_distance, 'steer': steer,
            'throttle': throttle, 'brake': brake}
