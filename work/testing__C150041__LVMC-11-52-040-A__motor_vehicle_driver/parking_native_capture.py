"""CARLA-lazy original body/heading/control frame serialization.

The caller owns the actor, world tick, camera capture and original file write.
"""
from __future__ import annotations

import json
import math


def capture_frame(vehicle, frame, time_s, carla_module):
    if type(frame) is not int or frame < 0:
        raise ValueError("original world frame must be a nonnegative integer")
    if type(time_s) not in (int, float) or not math.isfinite(time_s) or time_s < 0:
        raise ValueError("original world time must be finite and nonnegative")
    bbox = vehicle.bounding_box
    if bbox.extent.x <= 0 or bbox.extent.y <= 0:
        raise ValueError("vehicle bounding box must be positive")
    transform = vehicle.get_transform()
    vertices = []
    for along, across in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        local = carla_module.Location(x=bbox.location.x + along * bbox.extent.x,
                                      y=bbox.location.y + across * bbox.extent.y,
                                      z=bbox.location.z)
        world = transform.transform(local)
        vertices.append([float(world.x), float(world.y)])
    direction = transform.get_forward_vector()
    velocity = vehicle.get_velocity()
    control = vehicle.get_control()
    values = [value for point in vertices for value in point]
    values += [direction.x, direction.y, velocity.x, velocity.y, velocity.z,
               control.throttle, control.steer, control.brake]
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("Native body, direction, velocity or control is nonfinite")
    if not (0 <= control.throttle <= 1 and -1 <= control.steer <= 1 and
            0 <= control.brake <= 1):
        raise ValueError("Native control outside expected range")
    return {"frame": frame, "time_s": float(time_s),
            "body_vertices_xy_m": vertices,
            "vehicle_forward_xy": [float(direction.x), float(direction.y)],
            "speed_m_s": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
            "control": {"throttle": float(control.throttle),
                        "steer": float(control.steer), "brake": float(control.brake)}}


def append_frame(handle, record):
    """Append one original tick record to an already opened text file."""
    handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
