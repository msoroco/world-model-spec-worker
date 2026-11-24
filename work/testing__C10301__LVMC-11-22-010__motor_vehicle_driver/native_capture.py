"""Lazy frame-complete Native capture orchestration for alley observations.

The operator supplies a reviewed site and a Native adapter. This module never
creates a map feature or certifies attention from an exterior camera.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_operation import CASE_PROFILES, FPS, assemble_measurement_rows, request_control, sample_original, validate_history
from native_context import sample_from_native

CAMERAS = ("front", "rear", "left", "right")
FRAMES = 900


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture(adapter, actor, carla, site: dict, case_id: str, person_id: str,
            output: Path, frames: int = FRAMES) -> dict:
    """Request control, tick, read original state/context and four same-tick PNGs.

    Adapter API: tick() -> world snapshot; image(camera, frame) -> same-tick
    source packet containing PNG bytes, camera/sensor ID, frame and time;
    world, marking_reader, parking_reader, signal_reader, conflict_reader.
    A case-specific snapshot is written only after all frame sources validate.
    """
    if case_id not in CASE_PROFILES or frames != FRAMES or site.get("fps") != FPS:
        raise ValueError("exact 900-frame 20 Hz capture required")
    site_digest = site.get("site_source_sha256")
    if not isinstance(site_digest, str) or len(site_digest) != 64 or any(
            c not in "0123456789abcdef" for c in site_digest):
        raise ValueError("reviewed site source hash required")
    for key in ("alley_route_source_sha256", "access_aisle_source_sha256",
                "parking_designation_source_sha256", "municipal_jurisdiction_source_sha256"):
        digest = site.get(key)
        if not isinstance(digest, str) or len(digest) != 64 or any(
                c not in "0123456789abcdef" for c in digest):
            raise ValueError("reviewed site source hash required: " + key)
    if not person_id or not output.exists() or not output.is_dir():
        raise ValueError("operator identity and output directory required")
    ego_rows, context_rows, image_rows = [], [], []
    image_dir = output / "camera-png"
    image_dir.mkdir(exist_ok=False)
    for index in range(frames):
        request_control(actor, carla, case_id, index / FPS)
        snapshot = adapter.tick()
        ego = sample_original(actor, snapshot, case_id, person_id)
        context = sample_from_native(actor, adapter.world, snapshot, case_id, site,
                                     adapter.marking_reader, adapter.parking_reader,
                                     adapter.signal_reader, adapter.conflict_reader)
        cameras = {}
        for camera in CAMERAS:
            packet = adapter.image(camera, ego["native_frame"])
            if not isinstance(packet, dict) or packet.get("source_kind") != "original_native_camera" or packet.get("camera_id") != camera or packet.get("native_verified") is not True:
                raise ValueError("original Native camera packet required: " + camera)
            if packet.get("native_frame") != ego["native_frame"] or abs(packet.get("native_time_s", -1) - ego["native_time_s"]) > .001:
                raise ValueError("camera packet frame or time mismatch")
            if not isinstance(packet.get("sensor_id"), str) or not packet["sensor_id"]:
                raise ValueError("Native sensor identity required")
            data = packet.get("png")
            if not isinstance(data, bytes) or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("missing original PNG camera: " + camera)
            (image_dir / f"{index:04d}-{camera}.png").write_bytes(data)
            cameras[camera] = {"sha256": _sha(data), "sensor_id": packet["sensor_id"],
                               "native_frame": ego["native_frame"]}
        ego_rows.append(ego)
        context_rows.append(context)
        image_rows.append({"native_frame": ego["native_frame"],
                           "native_time_s": ego["native_time_s"], "cameras": cameras})
    validate_history(ego_rows, case_id)
    measurement_rows = assemble_measurement_rows(ego_rows, context_rows, case_id)
    for first, second in zip(image_rows, image_rows[1:]):
        if second["native_frame"] != first["native_frame"] + 1:
            raise ValueError("camera frame gap")
        if abs(second["native_time_s"] - first["native_time_s"] - 1 / FPS) > .001:
            raise ValueError("camera time gap")
    def write_rows(name, rows):
        raw = b"".join((json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode() for row in rows)
        (output / name).write_bytes(raw)
        return _sha(raw)
    hashes = {"ego": write_rows("ego.jsonl", ego_rows),
              "context": write_rows("context.jsonl", context_rows),
              "operation": write_rows("operation.jsonl", measurement_rows),
              "camera_frame_map": write_rows("camera-frame-map.jsonl", image_rows)}
    result = {"format": "worker-alley-native-capture", "case_id": case_id,
              "source_kind": "original_native_capture", "diagnostic_fixture": True,
              "fps": FPS, "duration_frames": FRAMES, "camera_ids": list(CAMERAS),
              "first_native_frame": ego_rows[0]["native_frame"],
              "last_native_frame": ego_rows[-1]["native_frame"],
              "source_sha256": hashes,
              "site_source_sha256": site.get("site_source_sha256"),
              "alley_route_source_sha256": site["alley_route_source_sha256"],
              "access_aisle_source_sha256": site["access_aisle_source_sha256"],
              "parking_designation_source_sha256": site["parking_designation_source_sha256"],
              "municipal_jurisdiction_source_sha256": site["municipal_jurisdiction_source_sha256"],
              "operation_source_sha256": hashes["operation"],
              "nominal_speed_m_s": 2.0,
              "requested_lateral_profile": CASE_PROFILES[case_id],
              "attention_state": "unobserved", "legal_judgment": "unresolved"}
    (output / "capture.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result
