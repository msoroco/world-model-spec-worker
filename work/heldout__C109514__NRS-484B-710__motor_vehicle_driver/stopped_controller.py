"""CARLA-lazy approach controller for an apparatus stopped beyond the junction.

The target centre distance is an engineering request. Original Native footprints
and motion state determine whether the drive-to branch actually occurred.
"""
from math import hypot, isfinite

FEET_PER_METRE = 3.280839895013123


def approach_step(ego, apparatus, *, target_distance_ft=500.0,
                  target_speed_mps=5.0, gain=0.35, steer=0.0,
                  carla_module=None):
    if any(not isfinite(float(value)) for value in
           (target_distance_ft, target_speed_mps, gain, steer)):
        raise ValueError("Approach controller parameters must be finite")
    if target_distance_ft <= 0 or target_speed_mps <= 0 or gain <= 0 or abs(steer) > .5:
        raise ValueError("Approach controller parameters are invalid")
    ego_transform, apparatus_transform = ego.get_transform(), apparatus.get_transform()
    heading = ego_transform.get_forward_vector()
    norm = hypot(float(heading.x), float(heading.y))
    if norm < 1e-9:
        raise ValueError("Ego heading is unavailable")
    forward = (heading.x / norm, heading.y / norm)
    displacement = (apparatus_transform.location.x - ego_transform.location.x,
                    apparatus_transform.location.y - ego_transform.location.y)
    ahead = displacement[0] * forward[0] + displacement[1] * forward[1]
    lateral = abs(displacement[0] * forward[1] - displacement[1] * forward[0])
    if ahead <= 0 or lateral > 2.5:
        raise ValueError("Stopped apparatus is not ahead in the approach lane")
    distance = hypot(*displacement)
    speed = ego.get_velocity()
    along_speed = speed.x * forward[0] + speed.y * forward[1]
    if along_speed < -.1:
        raise ValueError("Approaching subject is reversing")
    error = distance - target_distance_ft / FEET_PER_METRE
    desired = min(target_speed_mps, max(0.0, gain * error))
    speed_error = desired - along_speed
    throttle = min(.6, max(0., .3 * speed_error))
    brake = min(.8, max(0., -.3 * speed_error))
    if error < 0:
        throttle = 0.
        brake = max(brake, .65)
    if carla_module is None:
        import carla as carla_module
    ego.apply_control(carla_module.VehicleControl(throttle=throttle,
                      brake=brake, steer=steer))
    return {"centre_distance_m": distance, "error_m": error,
            "subject_speed_mps": along_speed, "throttle": throttle,
            "brake": brake}
