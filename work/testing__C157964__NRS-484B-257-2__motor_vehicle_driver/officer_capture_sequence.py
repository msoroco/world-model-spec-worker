"""Synchronous 20 Hz Native capture construction for subsection 2 cases.

The source packet is checked before the first tick. This module retains raw
camera references and Native commands for each frame; later processing must
review original pixels and actor histories independently.
"""

import hashlib
import json
import math
from pathlib import Path

from officer_capture_step import step
from officer_native_sources import record as record_native_sources
from officer_source_intake import load_and_validate
from officer_site import validate_site


def run(carla, world, ego, officer, bone_adapter, case_id, *, frame_count,
        source_root, source_packet, other_actor, traffic_sampler, camera_readback,
        before_tick=None, after_tick=None):
    if type(frame_count) is not int or frame_count < 3:
        raise ValueError("Complete 20 Hz frame count required")
    settings = world.get_settings()
    delta = getattr(settings, "fixed_delta_seconds", None)
    if (getattr(settings, "synchronous_mode", None) is not True or
            type(delta) not in (float, int) or not math.isfinite(delta) or
            abs(delta - 0.05) > 1e-6):
        raise ValueError("Native 20 Hz synchronous settings required")
    packet_path = Path(source_packet)
    intake = load_and_validate(source_root, packet_path)
    validate_site(Path(source_root) / intake["source_paths"]["road"])
    if not callable(traffic_sampler):
        raise ValueError("Original traffic sampler required")
    rows = []
    previous_frame = -1
    previous_time = -math.inf
    for frame_index in range(frame_count):
        traffic = traffic_sampler(frame_index)
        if before_tick is not None:
            before_tick(frame_index)
        row = step(carla, world, ego, officer, bone_adapter, case_id,
                   frame_index, frame_count, traffic, camera_readback, intake)
        row["native_actor_source"] = record_native_sources(world, ego, other_actor, row)
        native_frame = row["carla_frame"]
        if native_frame <= previous_frame:
            raise ValueError("Native capture frames not strictly increasing")
        native_time = row["native_actor_source"]["time_s"]
        if native_time <= previous_time:
            raise ValueError("Native capture time not strictly increasing")
        previous_frame = native_frame
        previous_time = native_time
        rows.append(row)
        if after_tick is not None:
            after_tick(native_frame, native_time)
    return {"format": "worker-officer-subsection-2-native-capture",
            "case_id": case_id, "site_id": intake["site_id"],
            "source_packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "fixed_delta_seconds": 0.05, "frame_count": frame_count,
            "first_carla_frame": rows[0]["carla_frame"],
            "last_carla_frame": rows[-1]["carla_frame"],
            "rows": rows, "physical_visibility_judgment": "unreviewed",
            "police_authority_judgment": "unreviewed",
            "legal_exception_judgment": "unresolved"}


def write_receipt(capture, destination):
    """Persist a small text receipt only after every capture frame succeeded."""
    if not isinstance(capture, dict) or capture.get("format") != "worker-officer-subsection-2-native-capture":
        raise ValueError("Complete Native capture receipt required")
    if len(capture.get("rows", ())) != capture.get("frame_count"):
        raise ValueError("Incomplete Native capture rows")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(capture, sort_keys=True, separators=(",", ":")) + "\n")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
