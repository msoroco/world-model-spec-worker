"""Portable straight-lane truck following policy for a Native caller.

Commands target the same speed for both trucks. Actual gap persistence, traffic
interaction, safe occupancy and legal judgment must be measured after capture.
"""
import math


TARGET_SPEED_MPS = 12.0
LANE_CENTER_Y_M = -1.9
DT_S = 0.05


def command(actor, target_speed_mps=TARGET_SPEED_MPS, lane_center_y_m=LANE_CENTER_Y_M):
    if not math.isfinite(target_speed_mps) or target_speed_mps < 0:
        raise ValueError('Invalid truck target speed')
    velocity = actor.get_velocity()
    transform = actor.get_transform()
    forward = transform.get_forward_vector()
    speed = float(velocity.x) * float(forward.x) + float(velocity.y) * float(forward.y)
    lateral = float(transform.location.y) - lane_center_y_m
    heading = math.atan2(float(forward.y), float(forward.x))
    if any(not math.isfinite(x) for x in (speed, lateral, heading)):
        raise ValueError('Missing finite truck motion')
    speed_error = target_speed_mps - speed
    throttle = min(0.65, max(0.0, 0.25 * speed_error))
    brake = min(0.7, max(0.0, -0.30 * speed_error))
    steer = min(0.4, max(-0.4, -0.18 * lateral - 0.8 * heading))
    return {'throttle': throttle, 'brake': brake, 'steer': steer,
            'speed_mps': speed, 'lateral_error_m': lateral,
            'heading_error_rad': heading}


def apply_pair(ego, lead, control_factory):
    """Apply one frame's controls; caller owns 20 Hz ticking and source capture."""
    result = {}
    for name, actor in (('ego', ego), ('lead', lead)):
        values = command(actor)
        actor.apply_control(control_factory(throttle=values['throttle'],
                                            brake=values['brake'], steer=values['steer']))
        result[name] = values
    return result
