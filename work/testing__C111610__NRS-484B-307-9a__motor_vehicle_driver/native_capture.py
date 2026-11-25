"""Write one source-sealed original red-plus-green-arrow attempt.

The injected adapter owns CARLA actors, signal readbacks, world lease and cleanup.
This writer validates frame identity and preserves every original camera body.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import subprocess
from pathlib import Path

from PIL import Image

from native_turn import verify_site

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, raw):
    path.write_bytes(raw)
    return {"path": path.name, "sha256": _sha(raw)}


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def capture(adapter, site_path, profile_path, output, case_suffix,
            *, frame_count=600, on_frame=None):
    site_path, profile_path, output = map(Path, (site_path, profile_path, output))
    if output.exists() and any((output / name).exists() for name in
                                ("manifest.json", "site.json", "telemetry.json")):
        raise ValueError("original acquisition already exists")
    site_raw, profile_raw = site_path.read_bytes(), profile_path.read_bytes()
    site, profile = json.loads(site_raw), json.loads(profile_raw)
    verify_site(site, site_path.parent)
    if site.get("source_kind") != "original_native_site_review":
        raise ValueError("reviewed original Native site provenance missing")
    adapter_ref = site.get("adapter_source")
    if (not isinstance(adapter_ref, dict) or
            not isinstance(adapter_ref.get("path"), str) or
            not isinstance(adapter_ref.get("sha256"), str)):
        raise ValueError("reviewed original adapter source missing")
    adapter_path = (site_path.parent / adapter_ref["path"]).resolve()
    if (not adapter_path.is_relative_to(site_path.parent.resolve()) or
            not adapter_path.is_file() or
            _sha(adapter_path.read_bytes()) != adapter_ref["sha256"]):
        raise ValueError("reviewed original adapter source changed")
    if (frame_count != 600 or profile.get("fps") != 20 or
            profile.get("duration_frames") != 600 or
            profile.get("cameras") != list(CAMERAS) or
            set(profile.get("dimensions", {})) != set(CAMERAS)):
        raise ValueError("exact four-camera 600-frame 20 Hz profile required")
    for name in CAMERAS:
        dims = profile["dimensions"][name]
        if (not isinstance(dims, list) or len(dims) != 2 or
                any(type(value) is not int or value <= 0 for value in dims)):
            raise ValueError("four-camera source dimensions invalid: " + name)
    if not callable(getattr(adapter, "tick", None)) or not callable(
            getattr(adapter, "source_attestation", None)):
        raise ValueError("original Native adapter required")
    attestation = adapter.source_attestation()
    if (attestation.get("native_origin") is not True or
            attestation.get("site_sha256") != _sha(site_raw) or
            attestation.get("source_ref") != adapter_ref["path"] or
            attestation.get("adapter_sha256") != adapter_ref["sha256"]):
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
    adapter_destination = (output / adapter_ref["path"]).resolve()
    if not adapter_destination.is_relative_to(output.resolve()) or adapter_destination.exists():
        raise ValueError("reviewed adapter destination invalid")
    adapter_destination.parent.mkdir(parents=True, exist_ok=True)
    adapter_destination.write_bytes(adapter_path.read_bytes())
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
                if list(pixels.size) != profile["dimensions"][name]:
                    raise ValueError("original camera dimensions mismatch: " + name)
            path = output / f"{name}-{i:06d}.png"
            ref = _write(path, raw)
            camera_rows[name].append({"frame": i, "source": ref})
        if on_frame is not None:
            on_frame(i, original)
    manifest = {"case_suffix": case_suffix, "fps": 20,
                "duration_frames": 600, "site": site_ref,
                "camera_profile": profile_ref,
                "telemetry": _write(output / "telemetry.json", _json(rows)),
                "frame_map": _write(output / "frame_map.json", _json(frame_map)),
                "native_source_attestation": attestation,
                "cameras": camera_rows}
    return _write(output / "manifest.json", _json(manifest))


class OriginalVideo:
    """Encode only verified same-frame PNG bodies into four lossless source videos."""

    def __init__(self, output, profile):
        self.output = Path(output)
        self.processes = {}
        self.profile = profile
        for name in CAMERAS:
            width, height = profile["dimensions"][name]
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                       "-f", "image2pipe", "-vcodec", "png", "-r", "20",
                       "-i", "pipe:0", "-frames:v", "600", "-c:v", "ffv1",
                       "-level", "3", "-pix_fmt", "bgr0",
                       str(self.output / (name + ".mkv"))]
            self.processes[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                     stderr=subprocess.PIPE)

    def append(self, cameras):
        for name in CAMERAS:
            raw = cameras[name]["png_bytes"]
            self.processes[name].stdin.write(raw)

    def close(self):
        codes = {}
        for name, process in self.processes.items():
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            message = process.stderr.read().decode(errors="replace")
            codes[name] = process.wait()
            if codes[name]:
                raise RuntimeError("source video encoder failed: " + name + ": " + message)
        return codes
