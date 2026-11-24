"""Original Native pose readback for the emergency driver and pedestrian."""
from __future__ import annotations

import math


def sample_actor(actor, role: str) -> dict:
    if role not in ("ego", "pedestrian"):
        raise ValueError("Unknown original actor role")
    identity = getattr(actor, "id", None)
    if type(identity) is not int or identity < 0:
        raise ValueError("Original actor identity missing: " + role)
    pose = actor.get_transform()
    location = pose.location
    rotation = pose.rotation
    values = {
        "x_m": location.x, "y_m": location.y, "z_m": location.z,
        "roll_deg": rotation.roll, "pitch_deg": rotation.pitch,
        "yaw_deg": rotation.yaw,
    }
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in values.values()):
        raise ValueError("Original actor pose invalid: " + role)
    return {"role": role, "actor_id": identity, **values}
