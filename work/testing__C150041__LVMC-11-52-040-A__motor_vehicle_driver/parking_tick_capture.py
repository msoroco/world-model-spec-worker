"""Synchronized Native world-tick writer for C150041 original observations.

The caller owns the world, actors, PipelineCapture, cameras and FrameMap.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from parking_cameras import CAMERAS
from parking_control import apply, step
from parking_native_capture import append_frame, capture_frame


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _state(vehicle):
    transform = vehicle.get_transform()
    direction = transform.get_forward_vector()
    velocity = vehicle.get_velocity()
    return {"center_xy_m": [transform.location.x, transform.location.y],
            "forward_xy": [direction.x, direction.y],
            "speed_m_s": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)}


def capture_ticks(world, vehicle, scene, output, carla, pipeline_capture,
                  cameras, frame_map, *, sample_count=None):
    root = Path(__file__).resolve().parents[2]
    scratch = (root / ".runtime-work").resolve()
    output = Path(output).resolve()
    if not output.is_dir() or not output.is_relative_to(scratch):
        raise ValueError("fresh attempt under .runtime-work required")
    plan = scene["capture_plan"]
    if (plan.get("profile") != "overview1080-capability" or
            plan.get("rate_hz") != 20 or
            plan.get("cameras") != list(CAMERAS)):
        raise ValueError("four-camera capture plan differs")
    expected = round(plan["duration_s"] * plan["rate_hz"])
    count = expected if sample_count is None else sample_count
    if type(count) is not int or count <= 0 or count > expected:
        raise ValueError("capture sample count invalid")
    frames = []
    paths = {name: output / name for name in
             ("parking-history.jsonl", "camera-frame-map.jsonl", "controller-history.jsonl")}
    with paths["parking-history.jsonl"].open("x", buffering=1) as history, \
         paths["camera-frame-map.jsonl"].open("x", buffering=1) as camera_map, \
         paths["controller-history.jsonl"].open("x", buffering=1) as controller:
        for _ in range(count):
            request = step(scene, _state(vehicle))
            apply(vehicle, request, carla)
            frame = world.tick()
            snapshot = world.get_snapshot()
            if frame != snapshot.frame:
                raise RuntimeError("Native world frame mismatch")
            time_s = snapshot.timestamp.elapsed_seconds
            pipeline_capture.capture(frame, time_s)
            cameras.append(frame)
            frame_map.append(frame, time_s)
            original = capture_frame(vehicle, frame, time_s, carla)
            append_frame(history, original)
            common = {"frame": frame, "time_s": time_s}
            camera_map.write(json.dumps({**common, "camera_names": list(CAMERAS),
                                         "source_path": "video_frames.jsonl"},
                                        allow_nan=False) + "\n")
            controller.write(json.dumps({**common, "request": request},
                                        allow_nan=False) + "\n")
            frames.append(frame)
    return {"frames": frames, "source_hashes": {name: _sha(path) for name, path in paths.items()},
            "physical_acceptance_claimed": False}
