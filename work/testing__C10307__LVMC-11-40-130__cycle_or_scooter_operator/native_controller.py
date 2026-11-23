"""Lazy Native bicycle route controller with measured-motion rejection.

This controls a verified dynamic bicycle asset. It does not infer that a CARLA
blueprint represents a human-powered bicycle; native_spawn gates that source.
"""
from __future__ import annotations

import math
import json
from pathlib import Path

from native_geometry import ROUTE_END_X_M, ROUTE_START_X_M, ROUTE_Y_M


FPS = 20
DT_S = 1 / FPS
ASSIGNMENT_ID = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"


def exact_case_target(plan_path: Path, case_id: str) -> float:
    """Bind the controller speed to one exact reviewed construction case."""
    plan = json.loads(Path(plan_path).read_text())
    if (plan.get("assignment_id"), plan.get("cell_id"), plan.get("law_id")) != (
            ASSIGNMENT_ID, "C10307", "LVMC-11-40-130"):
        raise ValueError("controller plan identity mismatch")
    matching = [c for c in plan.get("cases", []) if c.get("case_id") == case_id]
    if len(matching) != 1 or not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("unknown exact bicycle case")
    case = matching[0]
    setup = case.get("world_setup", {})
    if (setup.get("layout"), setup.get("maneuver"), setup.get("control"),
            setup.get("bicycle")) != ("alley", "travel", "bicycle_rack",
                                       "human-powered, excluding moped"):
        raise ValueError("controller case does not preserve assigned alley bicycle scope")
    value = float(case.get("controller", {}).get("target_speed_mps", 0))
    if not math.isfinite(value) or not 0 < value <= 12:
        raise ValueError("invalid bicycle engineering speed target")
    return value


def target_velocity(carla, target_speed_mps: float):
    if not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 12:
        raise ValueError("invalid bicycle engineering speed target")
    return carla.Vector3D(x=target_speed_mps, y=0.0, z=0.0)


def run_bicycle_route(world, carla, bicycle, *, target_speed_mps: float,
                      max_frames: int = 600, lateral_tolerance_m: float = 0.8):
    """Apply velocity each synchronous tick and retain actual pose/velocity.

    Caller owns world restoration and actor destruction. This function fails if
    physics does not move the spawned body, it leaves the alley, or it never
    reaches the route endpoint. The result is software readback, not law review.
    """
    command = target_velocity(carla, target_speed_mps)
    if max_frames < 2 or not math.isfinite(lateral_tolerance_m) or not 0 < lateral_tolerance_m <= 1:
        raise ValueError("invalid route controller limits")
    first = bicycle.get_transform().location
    if abs(float(first.x) - ROUTE_START_X_M) > .5 or abs(float(first.y) - ROUTE_Y_M) > .5:
        raise ValueError("bicycle start outside checked route")
    origin_x = float(first.x)
    samples = []
    previous_x = float(first.x)
    previous_frame = None
    previous_time = None
    try:
        for index in range(max_frames):
            bicycle.set_target_velocity(command)
            frame_id = world.tick()
            snapshot = world.get_snapshot()
            native_frame = int(snapshot.frame)
            native_time = float(snapshot.timestamp.elapsed_seconds)
            if native_frame != int(frame_id) or not math.isfinite(native_time):
                raise ValueError("Native bicycle frame/time snapshot mismatch")
            if previous_frame is not None and (native_frame != previous_frame + 1 or
                    abs(native_time - previous_time - DT_S) > .005):
                raise ValueError("Native bicycle frame/time continuity failure")
            loc = bicycle.get_transform().location
            vel = bicycle.get_velocity()
            x, y = float(loc.x), float(loc.y)
            vx, vy, vz = float(vel.x), float(vel.y), float(vel.z)
            if not all(map(math.isfinite, (x, y, vx, vy, vz))):
                raise ValueError("nonfinite Native bicycle readback")
            if abs(y - ROUTE_Y_M) > lateral_tolerance_m:
                raise ValueError("Native bicycle left checked alley route")
            if x < previous_x - .05:
                raise ValueError("Native bicycle reversed on checked route")
            samples.append({"frame_id": native_frame, "time_s": native_time,
                            "x_m": x, "y_m": y,
                            "velocity_mps": [vx, vy, vz]})
            previous_x = x
            previous_frame = native_frame
            previous_time = native_time
            if index >= FPS and x - origin_x < .5:
                raise ValueError("Native bicycle failed measured-motion check")
            if x >= ROUTE_END_X_M:
                if len(samples) < FPS or max(s["x_m"] for s in samples) - samples[0]["x_m"] < 1:
                    raise ValueError("Native bicycle completion lacks motion history")
                return samples
        raise ValueError("Native bicycle did not complete checked alley route")
    finally:
        bicycle.set_target_velocity(carla.Vector3D(x=0.0, y=0.0, z=0.0))
