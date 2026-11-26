"""Original-frame interior gaze readback for a source-reviewed sensor.

This measures one observable and never infers a driver's legal attention state.
A caller must provide the reviewed sensor declaration and Native adapter; an
exterior camera or vehicle trajectory cannot stand in for this stream.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FPS = 20


def sample(adapter, actor, snapshot, case_id: str, sensor: dict) -> dict:
    if (not isinstance(sensor, dict) or sensor.get("review_status") != "reviewed"
            or sensor.get("observable") != "original_eyes_off_road_duration_s"
            or not sensor.get("sensor_id") or not sensor.get("source_sha256")):
        raise ValueError("source-reviewed original interior sensor required")
    packet = adapter.read_interior(actor, snapshot, sensor["sensor_id"])
    if not isinstance(packet, dict) or packet.get("source_kind") != "original_native_interior":
        raise ValueError("original Native interior packet required")
    frame = int(snapshot.frame)
    time = float(snapshot.timestamp.elapsed_seconds)
    if (packet.get("case_id") != case_id or packet.get("native_frame") != frame
            or abs(packet.get("native_time_s", -1) - time) > .001
            or packet.get("sensor_id") != sensor["sensor_id"]
            or packet.get("sensor_source_sha256") != sensor["source_sha256"]):
        raise ValueError("interior source frame, sensor or case mismatch")
    if type(packet.get("eyes_off_road")) is not bool or packet.get("native_verified") is not True:
        raise ValueError("original eyes-off-road readback missing")
    return {"source_kind": "original_native_interior", "case_id": case_id,
            "native_frame": frame, "native_time_s": time,
            "sensor_id": sensor["sensor_id"],
            "sensor_source_sha256": sensor["source_sha256"],
            "eyes_off_road": packet["eyes_off_road"], "native_verified": True}


def measure(path: Path, case_id: str, *, expected_frames: int = 900) -> dict:
    source = Path(path).read_bytes()
    rows = [json.loads(line) for line in source.splitlines()]
    if len(rows) != expected_frames or not rows:
        raise ValueError("complete original interior frame stream required")
    first = rows[0]
    sensor_id = first.get("sensor_id")
    sensor_sha = first.get("sensor_source_sha256")
    if not sensor_id or not isinstance(sensor_sha, str) or len(sensor_sha) != 64:
        raise ValueError("original interior sensor source identity missing")
    first_frame = first.get("native_frame")
    first_time = first.get("native_time_s")
    if type(first_frame) is not int or type(first_time) not in (float, int):
        raise ValueError("original interior frame origin missing")
    for index, row in enumerate(rows):
        if (row.get("source_kind") != "original_native_interior" or
                row.get("case_id") != case_id or row.get("sensor_id") != sensor_id or
                row.get("sensor_source_sha256") != sensor_sha or
                row.get("native_verified") is not True or
                type(row.get("eyes_off_road")) is not bool or
                row.get("native_frame") != first_frame + index or
                type(row.get("native_time_s")) not in (float, int) or
                not math.isfinite(row["native_time_s"]) or
                abs(row["native_time_s"] - first_time - index / FPS) > .001):
            raise ValueError("original interior frame join or sensor continuity failed")
    duration = sum(row["eyes_off_road"] for row in rows) / FPS
    return {"case_id": case_id, "source_sha256": hashlib.sha256(source).hexdigest(),
            "sensor_source_sha256": sensor_sha, "sensor_id": sensor_id,
            "original_frames": len(rows), "original_eyes_off_road_duration_s": duration,
            "attention_state": "unresolved", "legal_judgment": "unresolved",
            "physical_acceptance_claimed": False}
