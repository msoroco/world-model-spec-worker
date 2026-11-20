"""Lead-vehicle conflict-stop controller for a future Native exception probe.

This controller requests braking from current actor geometry and velocity. The
recorded cause and the statutory necessity judgment require original review.
"""
from math import cos, isfinite, radians, sin


def _vector(name, value):
    if not isinstance(value, (tuple, list)) or len(value) != 2 or any(
            type(item) not in (int, float) or not isfinite(item) for item in value):
        raise ValueError('Invalid '+name)
    return value


def decision(ego_xy_m, ego_velocity_xy_mps, lead_xy_m,
             lead_velocity_xy_mps, ego_heading_deg, *,
             same_path_half_width_m=1.8, stop_gap_m=6.0,
             deceleration_mps2=3.0, cruise_throttle=0.28):
    """Return a requested control and measured lead relation, without a verdict."""
    ego_xy_m = _vector('ego position', ego_xy_m)
    ego_velocity_xy_mps = _vector('ego velocity', ego_velocity_xy_mps)
    lead_xy_m = _vector('lead position', lead_xy_m)
    lead_velocity_xy_mps = _vector('lead velocity', lead_velocity_xy_mps)
    numbers = (ego_heading_deg, same_path_half_width_m, stop_gap_m,
               deceleration_mps2, cruise_throttle)
    if any(type(value) not in (int, float) or not isfinite(value)
           for value in numbers) or same_path_half_width_m <= 0 or \
            stop_gap_m <= 0 or deceleration_mps2 <= 0 or not 0 <= cruise_throttle <= 1:
        raise ValueError('Invalid conflict controller tuning')
    heading = radians(ego_heading_deg)
    forward_x, forward_y = cos(heading), sin(heading)
    dx, dy = lead_xy_m[0]-ego_xy_m[0], lead_xy_m[1]-ego_xy_m[1]
    longitudinal = dx*forward_x+dy*forward_y
    lateral = -dx*forward_y+dy*forward_x
    if longitudinal <= 0 or abs(lateral) > same_path_half_width_m:
        raise ValueError('Lead vehicle is not ahead on the observed path')
    ego_forward = ego_velocity_xy_mps[0]*forward_x+ego_velocity_xy_mps[1]*forward_y
    lead_forward = lead_velocity_xy_mps[0]*forward_x+lead_velocity_xy_mps[1]*forward_y
    closing = max(0.0, ego_forward-lead_forward)
    requested_braking_distance = stop_gap_m+closing*closing/(2*deceleration_mps2)
    brake_requested = longitudinal <= requested_braking_distance
    return {'lead_longitudinal_gap_m': longitudinal,
            'lead_lateral_offset_m': lateral,
            'closing_speed_mps': closing,
            'engineering_braking_distance_m': requested_braking_distance,
            'brake_requested_from_lead_relation': brake_requested,
            'throttle': 0.0 if brake_requested else cruise_throttle,
            'brake': 1.0 if brake_requested else 0.0,
            'physical_completion_claimed': False,
            'statutory_necessity_claimed': False}


def apply(ego, lead, carla, **tuning):
    ego_transform = ego.get_transform()
    lead_transform = lead.get_transform()
    ego_velocity = ego.get_velocity()
    lead_velocity = lead.get_velocity()
    requested = decision(
        (ego_transform.location.x, ego_transform.location.y),
        (ego_velocity.x, ego_velocity.y),
        (lead_transform.location.x, lead_transform.location.y),
        (lead_velocity.x, lead_velocity.y),
        ego_transform.rotation.yaw, **tuning)
    ego.apply_control(carla.VehicleControl(
        throttle=requested['throttle'], brake=requested['brake'],
        steer=0.0, hand_brake=False))
    return requested
