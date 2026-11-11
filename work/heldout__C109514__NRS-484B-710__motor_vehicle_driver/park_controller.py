"""CARLA-lazy approach and parking request near a stationary apparatus."""
from math import hypot, isfinite

FEET_PER_METRE = 3.280839895013123


def park_step(ego, apparatus, *, target_distance_ft=500, steer=0, carla_module=None):
    if not isfinite(target_distance_ft) or target_distance_ft <= 0 or not isfinite(steer) or abs(steer) > .5:
        raise ValueError('Invalid parking target or steering request')
    et, at = ego.get_transform(), apparatus.get_transform()
    heading = et.get_forward_vector()
    norm = hypot(float(heading.x), float(heading.y))
    if norm < 1e-9:
        raise ValueError('Parking subject heading is unavailable')
    forward = (heading.x / norm, heading.y / norm)
    dx, dy = at.location.x - et.location.x, at.location.y - et.location.y
    longitudinal = dx * forward[0] + dy * forward[1]
    lateral = abs(dx * forward[1] - dy * forward[0])
    if longitudinal <= 0 or lateral > 2.5:
        raise ValueError('Parked apparatus is not ahead in the approach lane')
    distance = hypot(dx, dy)
    velocity = ego.get_velocity()
    speed = velocity.x * forward[0] + velocity.y * forward[1]
    if speed < -.1:
        raise ValueError('Parking subject is reversing')
    error = distance - target_distance_ft / FEET_PER_METRE
    if error > .5:
        desired = min(3., max(0., .6 * error))
        throttle = min(.5, max(0., .35 * (desired - speed)))
        brake = min(.8, max(0., .35 * (speed - desired)))
        hand_brake = False
    elif speed > .15:
        throttle, brake, hand_brake = 0., .8, False
    else:
        throttle, brake, hand_brake = 0., 1., True
    if carla_module is None:
        import carla as carla_module
    ego.apply_control(carla_module.VehicleControl(throttle=throttle, brake=brake,
                      steer=steer, hand_brake=hand_brake))
    return {'centre_distance_m': distance, 'error_m': error,
            'subject_speed_mps': speed, 'parking_requested': hand_brake,
            'throttle': throttle, 'brake': brake}
