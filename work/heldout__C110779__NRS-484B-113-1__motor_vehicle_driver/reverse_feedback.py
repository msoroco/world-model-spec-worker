"""CARLA-independent closed-loop reverse controller for a sourced corridor.

The requested target is a point behind the vehicle. Native readbacks, rather
than this command, determine whether the backing movement was realized.
"""

from math import atan2, hypot, isfinite, pi


def _angle(value):
    return (value + pi) % (2 * pi) - pi


def command(position_xy, heading_rad, signed_speed_mps, target_xy,
            target_reverse_speed_mps, *, stop_radius_m=0.35):
    values = [*position_xy, heading_rad, signed_speed_mps, *target_xy,
              target_reverse_speed_mps, stop_radius_m]
    if len(position_xy) != 2 or len(target_xy) != 2 or not all(isfinite(float(v)) for v in values):
        raise ValueError('Finite original position, heading, speed and target required')
    if target_reverse_speed_mps <= 0 or stop_radius_m <= 0:
        raise ValueError('Reverse target speed and stop radius must be positive')
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    distance = hypot(dx, dy)
    if distance <= stop_radius_m:
        return {'reverse': True, 'throttle': 0.0, 'brake': 1.0, 'steer': 0.0,
                'target_reached': True}
    desired_heading = _angle(atan2(dy, dx) + pi)
    heading_error = _angle(desired_heading - heading_rad)
    # In reverse, yaw response has the opposite sign from steering input.
    steer = max(-0.8, min(0.8, -1.5 * heading_error))
    reverse_speed = max(0.0, -signed_speed_mps)
    error = target_reverse_speed_mps - reverse_speed
    throttle = max(0.0, min(0.55, 0.24 * error))
    brake = max(0.0, min(0.65, -0.3 * error))
    return {'reverse': True, 'throttle': throttle, 'brake': brake,
            'steer': steer, 'target_reached': False}
