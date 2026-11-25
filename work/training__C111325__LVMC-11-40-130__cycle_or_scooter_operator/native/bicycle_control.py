"""Measured-speed controller for an original bicycle stop-sign approach.

The target speed is an engineering setting. A saved original trace must report
realized velocity and position; this controller never makes a legal finding.
"""
import math

STOP_X_M = -2.0
FRAME_DT_S = 0.05
TARGETS_MPS = {'condition_a': 3.0, 'condition_b': 5.0}


def _finite(value, name):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Invalid Native ' + name)
    return float(value)


def command(condition, position_x_m, velocity_x_m, prior=None):
    """Compute throttle/brake from current Native readbacks before one tick."""
    if condition not in TARGETS_MPS:
        raise ValueError('Unknown bicycle speed condition')
    x = _finite(position_x_m, 'position')
    velocity = _finite(velocity_x_m, 'velocity')
    if prior is not None:
        previous_x = _finite(prior['position_x_m'], 'prior position')
        if x + 0.03 < previous_x or x - previous_x > 0.75:
            raise ValueError('Bicycle teleported or reversed on approach')
    gap = STOP_X_M - x
    if gap < -0.20:
        raise ValueError('Bicycle crossed planned stop position')
    target = min(TARGETS_MPS[condition], math.sqrt(max(0.0, 3.0 * gap)))
    error = target - max(0.0, velocity)
    throttle = min(0.8, max(0.0, 0.12 * error))
    brake = min(1.0, max(0.0, -0.45 * error))
    if gap <= 0.15:
        throttle = 0.0
        brake = 1.0
    return {'condition': condition, 'position_x_m': x,
            'velocity_x_mps': velocity, 'remaining_to_stop_m': gap,
            'target_speed_mps': target, 'throttle': throttle,
            'brake': brake, 'steer': 0.0,
            'legal_verdict': None}


def apply(bicycle, carla, condition, prior=None):
    """Read the actor and issue a bounded control; the caller owns the tick."""
    if bicycle.type_id != 'vehicle.bh.crossbike':
        raise ValueError('Original actor is not the selected bicycle blueprint')
    transform = bicycle.get_transform()
    velocity = bicycle.get_velocity()
    if abs(transform.location.y + 1.75) > 0.65 or abs(velocity.y) > 0.75:
        raise ValueError('Bicycle departed surveyed approach lane')
    row = command(condition, transform.location.x, velocity.x, prior)
    bicycle.apply_control(carla.VehicleControl(
        throttle=row['throttle'], brake=row['brake'], steer=0.0))
    row['actor_id'] = bicycle.id
    row['blueprint'] = bicycle.type_id
    row['position_y_m'] = _finite(transform.location.y, 'lateral position')
    row['velocity_y_mps'] = _finite(velocity.y, 'lateral velocity')
    row['source_kind'] = 'original_native_actor_readback'
    return row
