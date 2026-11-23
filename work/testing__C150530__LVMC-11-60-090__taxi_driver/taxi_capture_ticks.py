"""Synchronous Native tick loop joining taxi motion, original views and trace."""
from __future__ import annotations

import json
from pathlib import Path

from taxi_cameras import NAMES, RATE_HZ
from taxi_native_motion import RouteController, apply_step

DEFAULT_DURATION_S = 35.0


def capture_ticks(world, actor, carla, layout, output: Path, pipeline_capture,
                  cameras, frame_map, trace_writer, *, duration_s=DEFAULT_DURATION_S):
    if duration_s <= 0 or round(duration_s * RATE_HZ) != duration_s * RATE_HZ:
        raise ValueError("capture duration must contain whole 20 Hz frames")
    output = Path(output)
    if not output.is_dir() or trace_writer.root != output.resolve():
        raise ValueError("Native trace and camera attempt roots differ")
    if set(cameras.queues) != set(NAMES):
        raise ValueError("four original camera sources required")
    controller = RouteController(layout)
    count = int(duration_s * RATE_HZ)
    frames = []
    commands = output / "taxi-controller-history.jsonl"
    try:
        with commands.open("x", buffering=1) as stream:
            for _ in range(count):
                command = apply_step(actor, carla, controller)
                frame = world.tick()
                snapshot = world.get_snapshot()
                if frame != snapshot.frame:
                    raise RuntimeError("Native world/snapshot frame mismatch")
                time_s = snapshot.timestamp.elapsed_seconds
                pipeline_capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                original = trace_writer.record()
                if original["frame"] != frame or abs(original["time_s"] - time_s) > 1e-5:
                    raise RuntimeError("original trace/frame map join differs")
                stream.write(json.dumps({"frame": frame, "time_s": time_s,
                                         "control": command}, allow_nan=False) + "\n")
                frames.append(frame)
    except BaseException:
        if not trace_writer.closed:
            trace_writer.close(completed=False)
        raise
    complete = bool(command["finished"])
    seal = trace_writer.close(completed=complete)
    return {"frames": frames, "trace_seal": seal, "maneuver_completed": complete,
            "camera_names": list(NAMES), "physical_acceptance_claimed": False}
