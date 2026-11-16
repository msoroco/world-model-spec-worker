"""Lazy CARLA parking controller for the authored ordinary-vehicle pair.

Engineering braking and steering parameters do not encode LVMC legal cutoffs.
"""
import math


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def command(x_m, y_m, longitudinal_speed_mps, target_x_m, target_y_m,
            *, approach_speed_mps=6.0):
    values = (x_m, y_m, longitudinal_speed_mps, target_x_m,
              target_y_m, approach_speed_mps)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError('Parking controller needs finite measured pose and speed')
    if longitudinal_speed_mps < 0 or approach_speed_mps <= 0:
        raise ValueError('Parking controller speed or request invalid')
    remaining = target_x_m - x_m
    lateral = target_y_m - y_m
    stopping_distance = longitudinal_speed_mps ** 2 / 8.0 + 0.8
    steer = clamp(0.12 * lateral, -0.45, 0.45)
    if remaining <= stopping_distance:
        return {'throttle': 0.0, 'brake': 1.0,
                'steer': steer if remaining > 0.4 else 0.0,
                'phase': 'brake_to_park',
                'remaining_m': remaining}
    throttle = clamp(0.24 * (approach_speed_mps - longitudinal_speed_mps),
                     0.0, 0.55)
    brake = 0.0 if longitudinal_speed_mps <= approach_speed_mps else 0.35
    return {'throttle': throttle, 'brake': brake, 'steer': steer,
            'phase': 'approach', 'remaining_m': remaining}


def apply(actor, carla, target_x_m, target_y_m, *, approach_speed_mps=6.0):
    """Read Native state and apply one CARLA tick; import carla at the call site."""
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    speed = max(0.0, velocity.x * math.cos(math.radians(transform.rotation.yaw)) +
                velocity.y * math.sin(math.radians(transform.rotation.yaw)))
    decision = command(transform.location.x, transform.location.y, speed,
                       target_x_m, target_y_m,
                       approach_speed_mps=approach_speed_mps)
    actor.apply_control(carla.VehicleControl(throttle=decision['throttle'],
                                             brake=decision['brake'],
                                             steer=decision['steer']))
    return decision
