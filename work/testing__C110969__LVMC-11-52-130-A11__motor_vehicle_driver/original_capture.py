"""Lazy Native ego pose writer for a 45-second C110969 stop attempt.

The caller owns world setup, selected map/actor, four cameras, context capture,
restoration, and sealed acquisition. This module records source samples only.
"""

import hashlib
import json
import math
from pathlib import Path

from stop_controller import command


def capture_pose(world, ego, output, *, boundary, approach, target_gap_m,
                 vehicle_length_m, world_to_local, frame_count=900,
                 frame_observer=None):
    if frame_count != 900:
        raise ValueError("Exact case requires 900 original frames")
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - 0.05) > 1e-9:
        raise ValueError("Native world must be synchronous at 20 Hz")
    if target_gap_m < 0 or vehicle_length_m <= 0:
        raise ValueError("Invalid target or actor dimensions")
    output = Path(output)
    if output.exists():
        raise ValueError("Original source path already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    first_frame = None
    try:
        with output.open("x", encoding="utf-8") as stream:
            for frame in range(frame_count):
                world_frame = world.tick()
                if first_frame is None:
                    first_frame = world_frame
                if world_frame != first_frame + frame:
                    raise ValueError("Native world frame gap")
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                local_x, local_y, heading = world_to_local(transform)
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                if not all(math.isfinite(value) for value in
                           (local_x, local_y, heading, speed)):
                    raise ValueError("Nonfinite Native actor sample")
                request = command(boundary, approach, local_x, local_y, heading,
                                  speed, vehicle_length_m, target_gap_m)
                if request.observed_front_gap_m < -0.5:
                    raise ValueError("Vehicle entered intersection during stop attempt")
                sample = {"frame": frame, "world_frame": world_frame,
                          "time_s": frame / 20, "actor_id": str(ego.id),
                          "x_m": local_x, "y_m": local_y,
                          "heading_deg": heading, "speed_mps": speed,
                          "halt_state": speed <= 0.1 and request.brake > 0,
                          "requested_throttle": request.throttle,
                          "requested_brake": request.brake,
                          "observed_front_gap_m": request.observed_front_gap_m}
                if frame_observer is not None:
                    frame_observer(frame, world_frame, sample)
                stream.write(json.dumps(sample, sort_keys=True) + "\n")
                ego.apply_control(type(ego.get_control())(
                    throttle=request.throttle, brake=request.brake))
    finally:
        ego.apply_control(type(ego.get_control())(throttle=0.0, brake=1.0))
    return {"path": str(output),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "frame_count": frame_count, "first_world_frame": first_frame,
            "physical_acceptance_claimed": False}
