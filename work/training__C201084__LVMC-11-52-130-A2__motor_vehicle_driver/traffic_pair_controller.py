"""Common destination controller with an optional source-observed lead vehicle.

The destination is beyond the authored fire-lane segment. A lead-based braking
request may override the destination request. Neither request proves necessity.
"""
from math import isfinite

from conflict_controller import decision as lead_decision
from native_controller import command as destination_command


def request(ego_xy_m, ego_yaw_deg, ego_velocity_xyz_mps,
            destination_xy_m, *, lead_xy_m=None,
            lead_velocity_xyz_mps=None, stop_radius_m=0.8,
            cruise_mps=4.0, destination_deceleration_mps2=2.0,
            same_path_half_width_m=1.8, lead_stop_gap_m=6.0,
            lead_deceleration_mps2=3.0, lead_cruise_throttle=0.28):
    """Compute one deterministic control from retained actor state."""
    if (len(destination_xy_m) != 2 or any(type(v) not in (int,float) or
            not isfinite(v) for v in destination_xy_m)):
        raise ValueError('Traffic-pair destination must be finite')
    base = destination_command(ego_xy_m, ego_yaw_deg,
                               ego_velocity_xyz_mps, destination_xy_m,
                               stop_radius_m=stop_radius_m,
                               cruise_mps=cruise_mps,
                               deceleration_mps2=destination_deceleration_mps2)
    if (lead_xy_m is None) != (lead_velocity_xyz_mps is None):
        raise ValueError('Lead pose and velocity must both be present or absent')
    lead = None
    if lead_xy_m is not None:
        lead = lead_decision(ego_xy_m, ego_velocity_xyz_mps[:2],
                             lead_xy_m, lead_velocity_xyz_mps[:2],
                             ego_yaw_deg,
                             same_path_half_width_m=same_path_half_width_m,
                             stop_gap_m=lead_stop_gap_m,
                             deceleration_mps2=lead_deceleration_mps2,
                             cruise_throttle=lead_cruise_throttle)
    override = bool(lead and lead['brake_requested_from_lead_relation'])
    return {
        'throttle': 0.0 if override else base['throttle'],
        'brake': 1.0 if override else base['brake'],
        'steer': base['steer'],
        'hand_brake': base['hand_brake'] if not override else False,
        'control_basis': 'observed_lead_braking_request' if override else
                         'common_destination_request',
        'destination_xy_m': list(destination_xy_m),
        'destination_distance_m': base['distance_to_target_m'],
        'destination_phase': base['phase'],
        'lead_present': lead is not None,
        'lead_relation': lead,
        'physical_completion_claimed': False,
        'statutory_necessity_claimed': False,
    }


def apply(ego, lead, carla, destination_xy_m, **tuning):
    transform = ego.get_transform()
    velocity = ego.get_velocity()
    lead_transform = lead.get_transform() if lead is not None else None
    lead_velocity = lead.get_velocity() if lead is not None else None
    requested = request(
        [transform.location.x, transform.location.y],
        transform.rotation.yaw,
        [velocity.x, velocity.y, velocity.z],
        destination_xy_m,
        lead_xy_m=[lead_transform.location.x, lead_transform.location.y]
            if lead_transform is not None else None,
        lead_velocity_xyz_mps=[lead_velocity.x, lead_velocity.y, lead_velocity.z]
            if lead_velocity is not None else None,
        **tuning)
    ego.apply_control(carla.VehicleControl(**{key: requested[key] for key in
        ('throttle','brake','steer','hand_brake')}))
    return requested
