"""Write one source-sealed original red-plus-green-arrow attempt.

The injected adapter owns CARLA actors, signal readbacks, world lease and cleanup.
This writer validates frame identity and preserves every original camera body.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

from native_turn import verify_site

CAMERAS = ("front", "left", "right", "rear")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, raw):
    path.write_bytes(raw)
    return {"path": path.name, "sha256": _sha(raw)}


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def capture(adapter, site_path, profile_path, output, case_suffix,
            *, frame_count=600):
    site_path, profile_path, output = map(Path, (site_path, profile_path, output))
    if output.exists() and any(output.iterdir()):
        raise ValueError("original attempt directory must be empty")
    site_raw, profile_raw = site_path.read_bytes(), profile_path.read_bytes()
    site, profile = json.loads(site_raw), json.loads(profile_raw)
    verify_site(site, site_path.parent)
    if (frame_count != 600 or profile.get("fps") != 20 or
            profile.get("duration_frames") != 600 or
            profile.get("cameras") != list(CAMERAS)):
        raise ValueError("exact four-camera 600-frame 20 Hz profile required")
    if not callable(getattr(adapter, "tick", None)) or not callable(
            getattr(adapter, "source_attestation", None)):
        raise ValueError("original Native adapter required")
    attestation = adapter.source_attestation()
    if (attestation.get("native_origin") is not True or
            attestation.get("site_sha256") != _sha(site_raw) or
            not attestation.get("source_ref")):
        raise ValueError("original Native site attestation mismatch")
    output.mkdir(parents=True, exist_ok=True)
    for ref in site["original_sources"].values():
        source = (site_path.parent / ref["path"]).resolve()
        if source.parent != site_path.parent.resolve() or not source.is_file():
            raise ValueError("original site source path invalid")
        destination = output / ref["path"]
        if destination.exists():
            raise ValueError("original site source destination collides")
        destination.write_bytes(source.read_bytes())
    site_ref = _write(output / "site.json", site_raw)
    profile_ref = _write(output / "camera_profile.json", profile_raw)
    rows, frame_map = [], []
    camera_rows = {name: [] for name in CAMERAS}
    first_time = None
    previous_frame = None
    for i in range(frame_count):
        original = adapter.tick()
        frame = original.get("native_frame")
        time = original.get("native_elapsed_s")
        if (type(frame) is not int or type(time) not in (int, float)
                or not math.isfinite(time) or
                (previous_frame is not None and frame != previous_frame + 1)):
            raise ValueError("original Native frame identity gap")
        previous_frame = frame
        if first_time is None:
            first_time = time
        if abs(time - first_time - i / 20) > 0.001:
            raise ValueError("original Native 20 Hz clock gap")
        telemetry = original.get("telemetry")
        if not isinstance(telemetry, dict) or telemetry.get("frame") != i:
            raise ValueError("original telemetry episode frame mismatch")
        rows.append(telemetry)
        frame_map.append({"frame": i, "native_frame": frame,
                          "native_elapsed_s": time})
        images = original.get("cameras")
        if not isinstance(images, dict) or set(images) != set(CAMERAS):
            raise ValueError("four original camera sources missing")
        for name in CAMERAS:
            image = images[name]
            if (not isinstance(image, dict) or image.get("frame") != frame
                    or not isinstance(image.get("png_bytes"), bytes)):
                raise ValueError("original camera frame mismatch: " + name)
            raw = image["png_bytes"]
            with Image.open(io.BytesIO(raw)) as pixels:
                if pixels.format != "PNG":
                    raise ValueError("original camera is not PNG: " + name)
                pixels.load()
                if pixels.size[0] <= 0 or pixels.size[1] <= 0:
                    raise ValueError("original camera dimensions invalid")
            path = output / f"{name}-{i:06d}.png"
            ref = _write(path, raw)
            camera_rows[name].append({"frame": i, "source": ref})
    manifest = {"case_suffix": case_suffix, "fps": 20,
                "duration_frames": 600, "site": site_ref,
                "camera_profile": profile_ref,
                "telemetry": _write(output / "telemetry.json", _json(rows)),
                "frame_map": _write(output / "frame_map.json", _json(frame_map)),
                "native_source_attestation": attestation,
                "cameras": camera_rows}
    return _write(output / "manifest.json", _json(manifest))
