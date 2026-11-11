"""CARLA-lazy controller for the NRS 484B.710 traveling boundary case.

The target is an engineering command. The retained Native full-footprint history,
not this command, supplies the actual 500 ft observation.
"""

from __future__ import annotations

from math import hypot, isfinite

FEET_PER_METRE = 3.280839895013123


def _xy(vector):
    return float(vector.x), float(vector.y)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def along_lane_gap(ego, apparatus):
    """Measure front-to-rear projected box clearance in ego's travel direction.

    This online feedback measure assumes approximately aligned actors. Saved
    processing must use all four measured ground corners instead.
    """
    e_transform, a_transform = ego.get_transform(), apparatus.get_transform()
    heading = _xy(e_transform.get_forward_vector())
    norm = hypot(*heading)
    if not isfinite(norm) or norm < 1e-9:
        raise ValueError("Ego has no usable forward vector")
    heading = (heading[0] / norm, heading[1] / norm)
    other_heading = _xy(a_transform.get_forward_vector())
    other_norm = hypot(*other_heading)
    if not isfinite(other_norm) or other_norm < 1e-9:
        raise ValueError("Apparatus has no usable forward vector")
    other_heading = (other_heading[0] / other_norm, other_heading[1] / other_norm)
    if _dot(heading, other_heading) < 0.98:
        raise ValueError("Following controller requires aligned travel directions")
    e_center, a_center = _xy(e_transform.location), _xy(a_transform.location)
    longitudinal = _dot((a_center[0] - e_center[0], a_center[1] - e_center[1]), heading)
    lateral = abs((a_center[0] - e_center[0]) * heading[1] -
                  (a_center[1] - e_center[1]) * heading[0])
    e_half = float(ego.bounding_box.extent.x)
    a_half = float(apparatus.bounding_box.extent.x)
    if any(not isfinite(value) or value < 0 for value in (e_half, a_half)):
        raise ValueError("Invalid actor length")
    if longitudinal <= 0 or lateral > 2.5:
        raise ValueError("Actors are not in a following lane configuration")
    return {"projected_gap_m": longitudinal - e_half - a_half,
            "centre_distance_m": hypot(a_center[0] - e_center[0], a_center[1] - e_center[1]),
            "lateral_offset_m": lateral}


def control_step(ego, apparatus, *, target_gap_ft=500.0, target_speed_mps=8.0,
                 gain=0.18, speed_gain=0.30, carla_module=None):
    """Apply one bounded control step; caller owns tick cadence and cleanup."""
    if any(not isfinite(float(value)) for value in
           (target_gap_ft, target_speed_mps, gain, speed_gain)):
        raise ValueError("Controller parameters must be finite")
    if target_gap_ft <= 0 or target_speed_mps <= 0 or gain <= 0 or speed_gain <= 0:
        raise ValueError("Controller parameters must be positive")
    if carla_module is None:
        import carla as carla_module  # Imported only during a real Native launch.
    gap = along_lane_gap(ego, apparatus)
    e_velocity, a_velocity = _xy(ego.get_velocity()), _xy(apparatus.get_velocity())
    heading = _xy(ego.get_transform().get_forward_vector())
    norm = hypot(*heading)
    heading = (heading[0] / norm, heading[1] / norm)
    ego_speed, apparatus_speed = _dot(e_velocity, heading), _dot(a_velocity, heading)
    if min(ego_speed, apparatus_speed) < -0.1:
        raise ValueError("Following controller cannot command reversing actors")
    error_m = gap["projected_gap_m"] - target_gap_ft / FEET_PER_METRE
    desired_speed = min(target_speed_mps, max(0.0, apparatus_speed + gain * error_m))
    speed_error = desired_speed - ego_speed
    throttle = min(0.65, max(0.0, speed_gain * speed_error))
    brake = min(0.8, max(0.0, -speed_gain * speed_error))
    if error_m < -2.0:
        throttle = 0.0
        brake = max(brake, min(0.8, -0.06 * error_m))
    control = carla_module.VehicleControl(throttle=throttle, brake=brake, steer=0.0)
    ego.apply_control(control)
    return {**gap, "command_target_gap_ft": target_gap_ft,
            "gap_error_m": error_m, "ego_speed_mps": ego_speed,
            "apparatus_speed_mps": apparatus_speed,
            "throttle": throttle, "brake": brake}
