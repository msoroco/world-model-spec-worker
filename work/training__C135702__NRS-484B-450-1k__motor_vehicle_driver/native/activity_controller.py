"""Finite Native controller requests for stop, stand and park probes.

These timing profiles distinguish software trajectories. They do not define
the statutory words or prove the operator's observed activity.
"""
from __future__ import annotations

from branch_context import ACTIVITIES
from geometry import FRAME_COUNT


def command(activity: str, frame: int) -> dict:
    if activity not in ACTIVITIES or not isinstance(frame, int) or not 0 <= frame < FRAME_COUNT:
        raise ValueError("Unknown activity or Native frame")
    if activity == "stop":
        phase = "approach" if frame < 60 else "halt" if frame < 140 else "departure"
    elif activity == "stand":
        phase = "approach" if frame < 60 else "standing_request" if frame < 440 else "departure"
    else:
        phase = "approach" if frame < 60 else "parking_request"
    if phase == "approach":
        return {"phase": phase, "throttle": .12, "brake": 0.0, "hand_brake": False}
    if phase == "departure":
        return {"phase": phase, "throttle": .18, "brake": 0.0, "hand_brake": False}
    return {"phase": phase, "throttle": 0.0, "brake": 1.0,
            "hand_brake": phase == "parking_request"}


def apply(vehicle, control_type, activity: str, frame: int) -> dict:
    """Exercise a CARLA-shaped apply_control call without importing CARLA."""
    row = command(activity, frame)
    vehicle.apply_control(control_type(throttle=row["throttle"], brake=row["brake"],
                                       hand_brake=row["hand_brake"]))
    return row
