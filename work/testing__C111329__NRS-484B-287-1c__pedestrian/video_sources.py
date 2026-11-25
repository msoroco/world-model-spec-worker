"""Encode all sealed original PNG camera frames as lossless 20 Hz sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

from native_observation import CAMERAS


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode_original_cameras(observation_path: str | Path, *, ffmpeg="ffmpeg") -> dict:
    """Convert camera archives after capture; temporary PNGs stay in the attempt."""
    observation_path = Path(observation_path).resolve()
    root = observation_path.parent
    document = json.loads(observation_path.read_text())
    frames = document.get("frames")
    sources = document.get("camera_sources")
    if not isinstance(frames, list) or len(frames) < 2 or \
       not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError("four original camera archives required")
    encoded = {}
    for name in CAMERAS:
        source = Path(sources[name]["path"]).resolve()
        target = root / (name + ".mkv")
        scratch = root / ("camera-encode-" + name)
        if source.parent != root or target.exists() or scratch.exists() or \
           _sha(source) != sources[name]["sha256"]:
            raise ValueError("original camera source changed or output exists: " + name)
        scratch.mkdir()
        try:
            with ZipFile(source) as archive:
                members = [f"{row['frame']:08d}.png" for row in frames]
                if archive.namelist() != members:
                    raise ValueError("original camera frame order differs: " + name)
                for index, (row, member) in enumerate(zip(frames, members)):
                    payload = archive.read(member)
                    if hashlib.sha256(payload).hexdigest() != \
                       row["camera_frames"][name]["sha256"]:
                        raise ValueError("original camera frame hash differs: " + name)
                    (scratch / f"{index:08d}.png").write_bytes(payload)
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                "-y", "-framerate", "20", "-start_number", "0", "-i",
                str(scratch / "%08d.png"), "-an", "-c:v", "ffv1",
                "-level", "3", str(target)]
            subprocess.run(command, check=True, timeout=1800,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            encoded[name] = {"path": str(target),
                             "sha256": _sha(target),
                             "frame_count": len(frames), "fps": 20}
        finally:
            shutil.rmtree(scratch)
    return encoded
