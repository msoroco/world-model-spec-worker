"""Run one source-bound C227824 Native tick sequence on an existing CARLA world.

The caller supplies a reviewed scene, a fresh private attempt, and a four-view
recorder. This module records original packets but does not seal the attempt or
claim a physical/legal result. Any failure leaves the attempt unsealed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from native_packets import PacketWriter, sample_tick
from native_signal import bind, configure
from saved_entry import CAMERAS
from walker_control import request


def _validate(scene, ticks):
    if not isinstance(scene, dict) or not isinstance(scene.get("case_id"), str):
        raise ValueError("exact Native scene and case identity required")
    if scene.get("entry_request") not in {"entry", "wait"}:
        raise ValueError("exact entry or wait request required")
    if not isinstance(ticks, int) or not 3 <= ticks <= 2400:
        raise ValueError("Native attempt needs 3 to 2400 original ticks")
    step = scene.get("fixed_delta_seconds")
    if not isinstance(step, (int, float)) or not math.isfinite(step) or abs(step - .05) > 1e-9:
        raise ValueError("20 Hz synchronous scene required")


def run(world, carla, scene, walker, recorder, attempt, *, ticks):
    """Apply controls and retain synchronized original body/signal/video joins.

    Recorder contract: ``capture(frame)`` waits for four current CARLA images,
    ``append(images)`` writes exactly those four images to video, and ``close()``
    waits for all encoders. The caller must independently decode and seal the
    resulting videos before using the attempt as Native evidence.
    """
    _validate(scene, ticks)
    root = Path(attempt).resolve()
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("fresh empty Native attempt directory required")
    writer = None
    failure = None
    try:
        head, devices = bind(world, scene)
        configuration = configure(head, devices, scene, carla)
        command = request(walker, carla, entry_request=scene["entry_request"],
                          target_xy_m=scene["target_xy_m"], speed_mps=scene["speed_mps"])
        (root / "scene.json").write_text(json.dumps(scene, sort_keys=True, allow_nan=False) + "\n")
        writer = PacketWriter(root)
        previous_frame = None
        previous_time = None
        for _ in range(ticks):
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("original world tick/snapshot frame differs")
            time_s = snapshot.timestamp.elapsed_seconds
            if previous_frame is not None:
                if frame != previous_frame + 1 or abs(time_s - previous_time - .05) > .005:
                    raise ValueError("original world frames not consecutive at 20 Hz")
            images = recorder.capture(frame)
            if not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise ValueError("four original camera images required")
            packets = sample_tick(scene, walker, head, devices, snapshot, images)
            recorder.append(images)
            writer.append(packets)
            previous_frame, previous_time = frame, time_s
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if writer is not None:
            writer.close()
        try:
            recorder.close()
        except BaseException:
            if failure is None:
                raise
    return {"case_id": scene["case_id"], "frame_count": ticks,
            "first_frame": previous_frame - ticks + 1,
            "last_frame": previous_frame, "signal_configuration": configuration,
            "walker_request": command, "native_capture_sealed": False,
            "actual_pixels_verified": False}
