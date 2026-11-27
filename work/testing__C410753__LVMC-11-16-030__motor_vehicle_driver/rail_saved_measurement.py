"""Saved-only admission of original railway crossing sources and camera frames."""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path

from rail_native_capture import CAMERAS
from rail_sight_measurement import measure


def _source(root, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("original rail source reference missing")
    root = Path(root).resolve()
    relative = Path(ref["path"])
    path = (root / relative).resolve()
    if (relative.is_absolute() or ".." in relative.parts or
            not path.is_relative_to(root) or not path.is_file() or
            any((root.joinpath(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1)) or
            hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256")):
        raise ValueError("original rail source missing or changed")
    return path


def verify_camera_row(root, row, frame):
    if (not isinstance(row, dict) or row.get("original_frame") != frame or
            not isinstance(row.get("sources"), dict) or
            set(row["sources"]) != set(CAMERAS)):
        raise ValueError("original rail four-camera/frame join differs")
    from PIL import Image
    hashes = {}
    for name, dimensions in CAMERAS.items():
        expected_path = f"original-cameras/{name}/{frame:08d}.png"
        if row["sources"][name].get("path") != expected_path:
            raise ValueError("original rail camera frame path differs")
        source = _source(root, row["sources"][name])
        raw = source.read_bytes()
        with Image.open(BytesIO(raw)) as image:
            if image.format != "PNG" or image.size != dimensions:
                raise ValueError("original rail camera profile differs")
            image.load()
        hashes[name] = row["sources"][name]["sha256"]
    return hashes


def verify_saved(root, packet, expected_case_id):
    """Recompute observations from retained originals, without running CARLA."""
    root = Path(root).resolve()
    receipt_path = root / "native-rail-receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("original rail receipt missing")
    receipt = json.loads(receipt_path.read_text())
    if (not isinstance(receipt, dict) or
            receipt.get("case_id") != expected_case_id or
            receipt.get("capture_kind") != "original_native" or
            (receipt.get("fps"), receipt.get("duration_s"), receipt.get("frame_count")) !=
            (20, 45, 900) or receipt.get("legal_conclusion") is not None):
        raise ValueError("original rail receipt identity or profile differs")
    reviewed_packet = json.loads(_source(root, receipt.get("packet")).read_text())
    if reviewed_packet != packet:
        raise ValueError("reviewed rail packet differs from original capture")
    frames = json.loads(_source(root, receipt.get("frames")).read_text())
    cameras = json.loads(_source(root, receipt.get("camera_map")).read_text())
    if not isinstance(frames, list) or not isinstance(cameras, list) or (
            len(frames), len(cameras)) != (900, 900):
        raise ValueError("original rail frame/camera count differs")
    for frame, camera in zip(frames, cameras):
        if not isinstance(frame, dict):
            raise ValueError("original rail frame row differs")
        verify_camera_row(root, camera, frame.get("original_frame"))
    map_source = _source(root, packet.get("original_map_source"))
    observation = measure(root, packet, map_source.read_text(), frames)
    if receipt.get("measurement") != observation:
        raise ValueError("retained rail measurement differs from originals")
    return {"case_id": expected_case_id, "source_complete": True,
            "original_frame_count": 900, "camera_views": list(CAMERAS),
            "observation": observation, "legal_conclusion": None}
