"""CARLA-lazy approach and parking control for a stopped fire apparatus.

The target is a construction command, not evidence of the realized distance.
Saved Native participant and state sources supply the branch measurement.
"""

from __future__ import annotations

from math import hypot, isfinite

FEET_PER_METRE = 3.280839895013123


def _xy(value):
    return float(value.x), float(value.y)


def approach_geometry(ego, apparatus):
    """Return centre distance and alignment for an actor approaching a stop."""
    ego_transform = ego.get_transform()
    apparatus_transform = apparatus.get_transform()
    forward = _xy(ego_transform.get_forward_vector())
    norm = hypot(*forward)
    if not isfinite(norm) or norm < 1e-9:
        raise ValueError("Ego has no usable approach direction")
    forward = (forward[0] / norm, forward[1] / norm)
    ego_xy, apparatus_xy = _xy(ego_transform.location), _xy(apparatus_transform.location)
    difference = (apparatus_xy[0] - ego_xy[0], apparatus_xy[1] - ego_xy[1])
    if any(not isfinite(value) for value in (*ego_xy, *apparatus_xy)):
        raise ValueError("Actor locations must be finite")
    longitudinal = difference[0] * forward[0] + difference[1] * forward[1]
    lateral = abs(difference[0] * forward[1] - difference[1] * forward[0])
    if longitudinal <= 0 or lateral > 2.5:
        raise ValueError("Stopped apparatus must be ahead in the approach lane")
    apparatus_velocity = _xy(apparatus.get_velocity())
    if not all(isfinite(value) for value in apparatus_velocity):
        raise ValueError("Apparatus velocity must be finite")
    if hypot(*apparatus_velocity) > 0.1:
        raise ValueError("Stopped-apparatus controller requires stationary apparatus")
    return {"centre_distance_m": hypot(*difference),
            "longitudinal_distance_m": longitudinal,
            "lateral_offset_m": lateral,
            "forward": forward}


def control_step(ego, apparatus, *, target_centre_ft, park=False,
                 cruise_speed_mps=8.0, gain=0.35, speed_gain=0.4,
                 carla_module=None):
    """Command a bounded approach or hold; caller owns the tick lifecycle.

    Parking is reported only after near-target speed has fallen below 0.15 m/s.
    The 0.5 m position band is a controller completion criterion, not a legal
    tolerance or proof that the realized separation is at the 500 ft boundary.
    """
    values = (target_centre_ft, cruise_speed_mps, gain, speed_gain)
    if any(not isfinite(float(value)) or float(value) <= 0 for value in values):
        raise ValueError("Controller parameters must be finite and positive")
    if type(park) is not bool:
        raise ValueError("Park mode must be a boolean")
    geometry = approach_geometry(ego, apparatus)
    velocity = _xy(ego.get_velocity())
    speed = velocity[0] * geometry["forward"][0] + velocity[1] * geometry["forward"][1]
    if not isfinite(speed) or speed < -0.1:
        raise ValueError("Approach controller cannot command reversing ego")
    error_m = geometry["centre_distance_m"] - target_centre_ft / FEET_PER_METRE
    desired_speed = min(cruise_speed_mps, max(0.0, gain * error_m))
    if error_m <= 0.5:
        desired_speed = 0.0
    speed_error = desired_speed - speed
    throttle = min(0.6, max(0.0, speed_gain * speed_error))
    brake = min(0.9, max(0.0, -speed_gain * speed_error))
    if error_m <= 0.5:
        throttle, brake = 0.0, max(0.4, brake)
    parked = bool(park and error_m <= 0.5 and abs(speed) < 0.15)
    if carla_module is None:
        import carla as carla_module  # Only a Native launch imports CARLA.
    control = carla_module.VehicleControl(throttle=throttle, brake=brake,
                                           steer=0.0, hand_brake=parked)
    ego.apply_control(control)
    return {"command_target_centre_ft": target_centre_ft,
            "measured_centre_distance_m": geometry["centre_distance_m"],
            "distance_error_m": error_m, "ego_speed_mps": speed,
            "throttle": throttle, "brake": brake, "parked_command": parked}
