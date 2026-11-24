"""Saved-only verification of the exact original Native sight source.

It remeasures the source rows and checks the acquisition seal. It does not
claim camera coverage, physical sight validity, or a legal speed judgment.
"""
from __future__ import annotations

import json
from io import BytesIO
from hashlib import sha256
from pathlib import Path

from native_sight_capture import CAMERAS
from sight_measurement import evaluate


class SavedSightError(ValueError):
    pass


def verify_cameras(attempt: Path, receipt: dict, frames: list) -> dict:
    """Reopen and fully decode each sealed original camera PNG."""
    from PIL import Image
    if receipt.get("camera_capture") != "original_four_camera_png":
        raise SavedSightError("four original camera sources absent")
    if receipt.get("camera_map_path") != "native-camera-map.json":
        raise SavedSightError("original camera map path differs")
    source = attempt / "native-camera-map.json"
    if not source.is_file() or sha256(source.read_bytes()).hexdigest() != receipt.get("camera_map_sha256"):
        raise SavedSightError("original camera map missing or changed")
    rows = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != len(frames):
        raise SavedSightError("original camera frame count differs")
    for row, frame in zip(rows, frames):
        if (row.get("frame") != frame["frame"] or row.get("time_s") != frame["time_s"] or
                not isinstance(row.get("sources"), dict) or set(row["sources"]) != set(CAMERAS)):
            raise SavedSightError("original camera frame/time join differs")
        for name, dimensions in CAMERAS.items():
            item = row["sources"][name]
            expected = f"cameras/{name}/{frame['frame']:08d}.png"
            if item.get("path") != expected:
                raise SavedSightError("original camera source path differs")
            image_path = attempt / expected
            if not image_path.is_file():
                raise SavedSightError("original camera image absent")
            raw = image_path.read_bytes()
            if sha256(raw).hexdigest() != item.get("sha256"):
                raise SavedSightError("original camera image changed")
            try:
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "PNG" or image.size != dimensions:
                        raise SavedSightError("original camera profile differs")
                    image.load()
            except (OSError, ValueError) as exc:
                raise SavedSightError("original camera image cannot be fully decoded") from exc
    return {"camera_frames": len(rows), "camera_images_decoded": len(rows) * len(CAMERAS),
            "camera_sources_sha256": receipt["camera_map_sha256"]}


def verify(attempt: Path, expected_case: str) -> dict:
    source = attempt / "native-sight.json"
    receipt_path = attempt / "native-sight-receipt.json"
    if not source.is_file() or not receipt_path.is_file():
        raise SavedSightError("sealed original sight acquisition absent")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("source_path") != "native-sight.json":
        raise SavedSightError("source path differs from sealed acquisition")
    if receipt.get("source_sha256") != sha256(source.read_bytes()).hexdigest():
        raise SavedSightError("original sight source changed")
    packet = json.loads(source.read_text(encoding="utf-8"))
    if packet.get("case_id") != expected_case or receipt.get("case_id") != expected_case:
        raise SavedSightError("exact case identity differs")
    if receipt.get("recorded_only") is not True or receipt.get("capture_kind") != "original_native":
        raise SavedSightError("original Native capture required")
    if receipt.get("fps") != 20 or receipt.get("duration_s") != 45:
        raise SavedSightError("20 Hz, 45-second acquisition differs")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 900:
        raise SavedSightError("900 original sight frames required")
    if (frames[0].get("frame") != receipt.get("first_frame") or
            frames[-1].get("frame") != receipt.get("last_frame") or
            receipt.get("frame_count") != 900):
        raise SavedSightError("original frame receipt differs")
    def digest(value):
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        return sha256(raw).hexdigest()
    if digest(frames) != packet.get("frame_source_sha256"):
        raise SavedSightError("original frame seal differs")
    if digest([f["rays"] for f in frames]) != packet.get("ray_source_sha256"):
        raise SavedSightError("original ray seal differs")
    if digest([f["ego_speed_mps"] for f in frames]) != packet.get("speed_source_sha256"):
        raise SavedSightError("original speed seal differs")
    measured = evaluate(packet)
    if digest(measured) != digest(receipt.get("measurement")):
        raise SavedSightError("saved recomputation differs from Native receipt")
    cameras = (verify_cameras(attempt, receipt, frames)
               if receipt.get("camera_capture") == "original_four_camera_png" else None)
    return {"case_id": expected_case, "original_sight_join": "passed",
            "measurement": measured, "camera_capture": cameras or "unverified",
            "physical_visibility": "unverified", "legal_conclusion": None}
