"""Lazy Native acquisition for the exact bicycle instruction trace.

The operator supplies device and officer readers bound to original local actors.
This module records their readbacks; it does not create official authority facts.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from saved_instruction import FORMAT, FRAME_COUNT, measure
from native_cameras import FourCameraCapture


def capture(world, bike, device, case: dict, site: dict, site_sha256: str,
            device_reader, officer_reader, output: Path,
            camera_readers=None, camera_dimensions=None, control_step=None) -> dict:
    if output.exists():
        raise ValueError("original instruction output already exists")
    if not callable(device_reader) or not callable(officer_reader):
        raise ValueError("original device and officer readers required")
    if bike.type_id != site["bike_blueprint_id"] or str(device.id) != site["device_id"]:
        raise ValueError("original bicycle or device readback mismatch")
    rows = []
    cameras = (FourCameraCapture(output.parent, camera_readers, camera_dimensions)
               if camera_readers is not None else None)
    published = False
    try:
        for step in range(FRAME_COUNT):
            if control_step is not None:
                control_step(step / 20.0)
            tick_frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != tick_frame:
                raise ValueError("Native tick and snapshot frame mismatch")
            transform = bike.get_transform()
            forward = transform.get_forward_vector()
            extent = bike.bounding_box.extent.x
            if not math.isfinite(extent) or extent <= 0:
                raise ValueError("Native bicycle body extent unavailable")
            front_x = transform.location.x + forward.x * extent
            front_y = transform.location.y + forward.y * extent
            velocity = bike.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            device_state = device_reader(device, snapshot)
            officer = officer_reader(snapshot, bike)
            if not isinstance(officer, dict):
                raise ValueError("original officer reader returned no source packet")
            row = {
                "frame": snapshot.frame,
                "time_s": snapshot.timestamp.elapsed_seconds,
                "bike_id": str(bike.id),
                "bike_blueprint_id": bike.type_id,
                "device_id": str(device.id),
                "device_state": device_state,
                "bike_front_xy": [front_x, front_y],
                "bike_speed_mps": speed,
                "officer_actor_id": officer.get("actor_id"),
                "officer_authority_source": officer.get("authority_source"),
                "officer_recipient_id": officer.get("recipient_id"),
                "officer_command": officer.get("command"),
            }
            if cameras is not None:
                cameras.sample(row)
            rows.append(row)
    except Exception:
        if cameras is not None:
            cameras.abort()
        raise
    finally:
        # A failed acquisition must not leave a commanded bicycle moving.
        if hasattr(bike, "set_target_velocity"):
            velocity_type = type(bike.get_velocity())
            bike.set_target_velocity(velocity_type(x=0.0, y=0.0, z=0.0))
    packet = {"format": FORMAT, "source_kind": "original_native",
              "case_id": case["case_id"], "site_sha256": site_sha256,
              "samples": rows, "camera_capture_complete": cameras is not None}
    if cameras is not None:
        packet['camera_sources'] = cameras.finish()
    raw = (json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name(output.name + ".pending")
    if pending.exists():
        raise ValueError("pending original instruction output already exists")
    try:
        pending.write_bytes(raw)
        source_hash = hashlib.sha256(raw).hexdigest()
        value = measure(pending, source_hash, case, site, site_sha256)
        pending.replace(output)
        published = True
        return value
    finally:
        pending.unlink(missing_ok=True)
        if cameras is not None and not published:
            cameras.abort()
