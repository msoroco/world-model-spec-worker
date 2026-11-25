"""Saved-only full PNG audit for original pedestrian crossing frames.

The caller supplies an actual capture directory and a manifest produced from that
capture. This checker never substitutes diagnostic images for physical evidence.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image

from native_acquisition import CAMERAS, _sha

PROFILE_DIMENSIONS = {'overview': [1920, 1080], 'approach': [1280, 720],
                      'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}


def inventory_camera_sources(packet: dict, capture_root: Path) -> dict:
    """Describe the four original PNG streams without changing captured bytes.

    The Native writer must save ``<camera>/<original_frame:06d>.png`` beneath
    its capture root. The independent auditor reopens these same paths.
    """
    if packet.get("format") != "crossing-native-acquisition-v1" or packet.get("rows_sha256") != _sha(packet.get("rows")):
        raise ValueError("unsealed Native acquisition rows")
    root = capture_root.resolve(strict=True)
    sources = []
    for row in packet["rows"]:
        frame = row["original_frame"]
        for camera in CAMERAS:
            rel = f"{camera}/{frame:06d}.png"
            path = (root / rel).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("original camera PNG missing")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if row.get("camera_png_sha256") and row["camera_png_sha256"].get(camera) != sha:
                raise ValueError("original camera PNG differs from Native source hash")
            sources.append({"original_frame": frame, "camera": camera,
                            "path": rel, "sha256": sha})
    return {"format": "crossing-original-camera-png-v1", "case_id": packet["case_id"],
            "native_rows_sha256": packet["rows_sha256"], "sources": sources}


def audit_camera_sources(packet: dict, manifest: dict, capture_root: Path,
                         *, allow_diagnostic: bool = False) -> dict:
    if packet.get("format") != "crossing-native-acquisition-v1":
        raise ValueError("Native acquisition packet required")
    if packet.get("diagnostic") is not False and not allow_diagnostic:
        raise ValueError("diagnostic Native acquisition rejected for delivery")
    rows = packet.get("rows")
    if not isinstance(rows, list) or not rows or packet.get("rows_sha256") != _sha(rows):
        raise ValueError("unsealed Native acquisition rows")
    if packet.get("frame_count") != len(rows):
        raise ValueError("Native acquisition frame count mismatch")
    if manifest.get("format") != "crossing-original-camera-png-v1":
        raise ValueError("original camera manifest required")
    if manifest.get("case_id") != packet.get("case_id") or manifest.get("native_rows_sha256") != packet["rows_sha256"]:
        raise ValueError("camera manifest Native source binding mismatch")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != len(rows) * len(CAMERAS):
        raise ValueError("four-camera original PNG source count mismatch")
    root = capture_root.resolve(strict=True)
    expected = {(row["original_frame"], camera) for row in rows for camera in CAMERAS}
    actual = [(source.get("original_frame"), source.get("camera")) for source in sources]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError("four-camera original frame coverage mismatch")
    by_frame = {row["original_frame"]: row for row in rows}
    dimensions = {}
    pixel_sha256 = hashlib.sha256()
    for source in sources:
        frame, camera = source["original_frame"], source["camera"]
        if by_frame[frame].get("camera_frames", {}).get(camera) != frame:
            raise ValueError("camera PNG original frame join mismatch")
        native_png_hash = by_frame[frame].get("camera_png_sha256", {}).get(camera)
        if not allow_diagnostic and native_png_hash is None:
            raise ValueError("Native camera PNG source hash missing")
        rel = source.get("path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
            raise ValueError("camera PNG relative path required")
        path = (root / rel).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("camera PNG outside capture root")
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha != source.get("sha256"):
            raise ValueError("camera PNG source hash mismatch")
        if native_png_hash is not None and sha != native_png_hash:
            raise ValueError("camera PNG differs from Native source hash")
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "PNG":
                    raise ValueError("camera source is not PNG")
                image.load()
                rgb = image.convert("RGB")
                width, height = rgb.size
                pixels = rgb.tobytes()
        except (OSError, ValueError) as exc:
            raise ValueError("camera PNG full decode failed") from exc
        if width < 2 or height < 2 or not pixels:
            raise ValueError("camera PNG pixels or dimensions invalid")
        if not allow_diagnostic and [width, height] != PROFILE_DIMENSIONS[camera]:
            raise ValueError('original camera dimensions differ from capture profile')
        if camera in dimensions and dimensions[camera] != [width, height]:
            raise ValueError("camera PNG dimensions changed")
        dimensions[camera] = [width, height]
        pixel_sha256.update(f"{frame}:{camera}:".encode())
        pixel_sha256.update(pixels)
    return {"format": "crossing-camera-full-decode-receipt-v1",
            "case_id": packet["case_id"], "native_rows_sha256": packet["rows_sha256"],
            "source_manifest_sha256": _sha(manifest), "frame_count": len(rows),
            "decoded_png_count": len(sources), "camera_dimensions": dimensions,
            "decoded_pixel_sha256": pixel_sha256.hexdigest(),
            "diagnostic": packet.get("diagnostic")}
