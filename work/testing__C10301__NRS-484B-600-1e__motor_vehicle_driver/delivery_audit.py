"""Independent saved-source integrity audit for exact 80 mph attempts.

This is a preparation check. Hashes and frame joins do not establish actual
pixels, public-way status, physical completion, or a legal speed judgment.
"""

from __future__ import annotations

import hashlib
import math
import json
import subprocess
from pathlib import Path

from speed_boundary import EXPECTED_FRAMES, measure

CASE_PREFIX = "testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__"
CAMERAS = ("front", "front_left", "front_right", "rear")


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source document is not an object")
    return value


def _sealed(attempt: Path, entry: dict, label: str) -> tuple[Path, str]:
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise ValueError(f"{label} binding incomplete")
    name, digest = entry["path"], entry["sha256"]
    if (not isinstance(name, str) or not name or Path(name).is_absolute() or
            ".." in Path(name).parts or not isinstance(digest, str) or
            len(digest) != 64):
        raise ValueError(f"{label} binding invalid")
    path = attempt / name
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(attempt.resolve()):
        raise ValueError(f"{label} source missing or escapes attempt")
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != digest:
        raise ValueError(f"{label} source hash differs")
    return path, observed


def audit_integrity(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    """Require original trace, frame map, four media files, and receipt joins."""
    attempt = Path(attempt)
    if case_id not in {CASE_PREFIX + suffix for suffix in ("below", "equal", "above")}:
        raise ValueError("unknown exact case")
    index = _read(attempt / "capture-index.json")
    if (index.get("format") != "c10301-capture-index-v1" or
            index.get("case_id") != case_id or
            index.get("frame_count") != EXPECTED_FRAMES or
            type(index.get("diagnostic_fixture")) is not bool):
        raise ValueError("capture index identity or frame count differs")
    if index["diagnostic_fixture"] and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot enter delivery audit")
    site_binding = index.get('native_site')
    site_hash = None
    if site_binding is not None:
        site_path, site_hash = _sealed(attempt, site_binding, 'Native site')
        site = _read(site_path)
        if (site.get('format') != 'c10301-native-site-v1' or
                site.get('case_id') != case_id or
                site.get('cell_id') != 'C10301' or
                site.get('actor') != 'motor_vehicle_driver' or
                site.get('layout') != 'alley' or
                site.get('control') != 'access_aisle' or
                site.get('maneuver') != 'travel' or
                site.get('diagnostic_fixture') != index['diagnostic_fixture']):
            raise ValueError('Native site and capture index differ')
    speed = measure(attempt, case_id)
    if speed["diagnostic_fixture"] != index["diagnostic_fixture"]:
        raise ValueError("speed and capture provenance differ")
    motion_path, motion_hash = _sealed(attempt, index.get("native_motion"), "Native motion")
    motion = _read(motion_path)
    if (motion.get("format") != "c10301-native-motion-v1" or
            motion.get("case_id") != case_id or
            motion.get("native_run_id") != speed["native_run_id"] or
            motion.get("speed_source_sha256") != speed["source_sha256"] or
            motion.get("diagnostic_fixture") != index["diagnostic_fixture"] or
            motion.get("sample_count") != EXPECTED_FRAMES or
            type(motion.get("travel_m")) not in (int, float) or
            not math.isfinite(motion["travel_m"]) or
            motion["travel_m"] < 100 or
            motion.get("physical_acceptance_claimed") is not False):
        raise ValueError("Native motion and capture index differ")
    map_path, map_hash = _sealed(attempt, index.get("frame_map"), "frame map")
    frame_map = _read(map_path)
    frames = frame_map.get("frames")
    if (frame_map.get("case_id") != case_id or
            frame_map.get("native_run_id") != speed["native_run_id"] or
            not isinstance(frames, list) or len(frames) != EXPECTED_FRAMES):
        raise ValueError("original frame map incomplete")
    origin = frames[0].get("frame") if isinstance(frames[0], dict) else None
    if type(origin) is not int or origin < 0:
        raise ValueError("original frame origin invalid")
    for i, row in enumerate(frames):
        if (not isinstance(row, dict) or row.get("frame") != origin + i or
                row.get("camera_frames") != {camera: origin + i for camera in CAMERAS}):
            raise ValueError("camera and original frame join differs")
    camera_readback_hash = motion.get("camera_frame_readback_sha256")
    if camera_readback_hash is None and not allow_diagnostic:
        raise ValueError("original camera readback required for delivery")
    if site_binding is None and not allow_diagnostic:
        raise ValueError('original Native site source required for delivery')
    if camera_readback_hash is not None:
        readback_path = attempt / "camera-frame-readback.json"
        raw = readback_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != camera_readback_hash:
            raise ValueError("original camera readback hash differs")
        readback = json.loads(raw)
        if (readback.get("case_id") != case_id or
                readback.get("native_run_id") != speed["native_run_id"] or
                readback.get("frames") != frames):
            raise ValueError("original camera readback and frame map differ")
    cameras = index.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("four camera bindings required")
    camera_hashes = {}
    for camera in CAMERAS:
        _, camera_hashes[camera] = _sealed(attempt, cameras[camera], camera)
    return {"format": "c10301-source-integrity-v1", "case_id": case_id,
            "native_run_id": speed["native_run_id"], "frame_count": EXPECTED_FRAMES,
            "motion_sha256": motion_hash, "frame_map_sha256": map_hash,
            "native_site_sha256": site_hash,
            "camera_sha256": camera_hashes,
            "diagnostic_fixture": index["diagnostic_fixture"],
            "source_integrity_passed": True, "full_video_decode": False,
            "actual_pixels": False, "physical_completion": False,
            "legal_judgment": "unresolved"}


def audit_decoded_media(attempt: Path, case_id: str, *,
                        allow_diagnostic: bool = False) -> dict:
    """Fully decode each sealed original camera stream at 20 Hz for 900 frames.

    This validates file integrity and decodability, not scene content or legal
    visibility. The source-index audit runs first and resolves the exact paths.
    """
    integrity = audit_integrity(attempt, case_id,
                                allow_diagnostic=allow_diagnostic)
    index = _read(Path(attempt) / "capture-index.json")
    decoded = {}
    for camera in CAMERAS:
        path, digest = _sealed(Path(attempt), index["cameras"][camera], camera)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_frames", "-show_entries",
             "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
             "-of", "json", str(path)], capture_output=True, text=True,
            timeout=120, check=False)
        if probe.returncode or not probe.stdout:
            raise ValueError(f"{camera} media probe failed")
        try:
            streams = json.loads(probe.stdout)["streams"]
            stream, = streams
            numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
            valid = (stream["codec_name"] in
                     {"ffv1", "huffyuv", "png", "rawvideo"} and
                     type(stream["width"]) is int and stream["width"] > 0 and
                     type(stream["height"]) is int and stream["height"] > 0 and
                     denominator > 0 and numerator == 20 * denominator and
                     int(stream["nb_read_frames"]) == EXPECTED_FRAMES)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            valid = False
        if not valid:
            raise ValueError(f"{camera} media codec, dimensions, rate or frames differ")
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
             "-map", "0:v:0", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120, check=False)
        if decode.returncode:
            raise ValueError(f"{camera} full video decode failed")
        decoded[camera] = {"sha256": digest, "frames": EXPECTED_FRAMES,
                           "width": stream["width"],
                           "height": stream["height"],
                           "codec": stream["codec_name"]}
    return {**integrity, "full_video_decode": True,
            "decoded_cameras": decoded,
            "actual_pixels": False, "physical_completion": False}
