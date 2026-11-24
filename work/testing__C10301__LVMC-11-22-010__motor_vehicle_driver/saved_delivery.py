"""Independent original-source audit before local alley delivery promotion.

This never claims interior attention, legal compliance, or physical acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image

from native_capture import CAMERAS, FPS, FRAMES
from native_operation import CASE_PROFILES, assemble_measurement_rows, validate_history


def _read(path: Path, digest: str) -> list[dict]:
    if not path.is_file():
        raise ValueError("missing original source: " + path.name)
    raw = path.read_bytes()
    if not raw or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("original source hash mismatch: " + path.name)
    return [json.loads(line) for line in raw.splitlines()]


def audit(directory: Path, case_id: str, require_delivery: bool = False) -> dict:
    if case_id not in CASE_PROFILES:
        raise ValueError("unknown exact case")
    meta_path = directory / "capture.json"
    meta = json.loads(meta_path.read_text())
    if meta.get("format") != "worker-alley-native-capture" or meta.get("case_id") != case_id:
        raise ValueError("capture metadata exact case mismatch")
    if require_delivery and meta.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic capture cannot be delivered")
    if meta.get("source_kind") != "original_native_capture" or meta.get("fps") != FPS or meta.get("duration_frames") != FRAMES:
        raise ValueError("original 20 Hz capture contract mismatch")
    if meta.get("camera_ids") != list(CAMERAS):
        raise ValueError("four original cameras required")
    digests = meta.get("source_sha256", {})
    ego = _read(directory / "ego.jsonl", digests.get("ego"))
    context = _read(directory / "context.jsonl", digests.get("context"))
    operation = _read(directory / "operation.jsonl", digests.get("operation"))
    frame_map = _read(directory / "camera-frame-map.jsonl", digests.get("camera_frame_map"))
    if any(len(rows) != FRAMES for rows in (ego, context, operation, frame_map)):
        raise ValueError("900 original rows required in every source")
    validate_history(ego, case_id)
    if assemble_measurement_rows(ego, context, case_id) != operation:
        raise ValueError("operation history differs from original sources")
    if meta.get("first_native_frame") != ego[0]["native_frame"] or meta.get("last_native_frame") != ego[-1]["native_frame"]:
        raise ValueError("native frame range mismatch")
    for index, (row, original) in enumerate(zip(frame_map, ego)):
        if row.get("native_frame") != original["native_frame"] or abs(row.get("native_time_s", -1) - original["native_time_s"]) > .001:
            raise ValueError("camera frame map is not joined to original state")
        if set(row.get("cameras", {})) != set(CAMERAS):
            raise ValueError("four original camera frames required")
        for camera in CAMERAS:
            image_path = directory / "camera-png" / f"{index:04d}-{camera}.png"
            if not image_path.is_file():
                raise ValueError("missing original camera image")
            raw = image_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["cameras"][camera]:
                raise ValueError("original camera image hash mismatch")
            with Image.open(image_path) as image:
                if image.format != "PNG" or min(image.size) <= 0:
                    raise ValueError("invalid original camera format")
                image.load()
    return {"format": "worker-alley-saved-audit", "case_id": case_id,
            "original_frames": FRAMES, "decoded_original_pngs": FRAMES * len(CAMERAS),
            "source_sha256": digests, "diagnostic_fixture": meta["diagnostic_fixture"],
            "attention_state": "unobserved", "legal_judgment": "unresolved"}
