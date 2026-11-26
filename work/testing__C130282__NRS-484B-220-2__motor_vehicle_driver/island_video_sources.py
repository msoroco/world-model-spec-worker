"""Encode sealed original PNG camera frames as lossless 20 Hz video sources."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

from island_source import CAMERAS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode_original_cameras(receipt_path, trace_path, *, ffmpeg="ffmpeg"):
    receipt_path = Path(receipt_path).resolve()
    root = receipt_path.parent
    receipt = json.loads(receipt_path.read_text())
    rows = [json.loads(line) for line in Path(trace_path).read_text().splitlines()]
    sources = receipt.get("camera_sources", {})
    if len(rows) != 900 or set(sources) != set(CAMERAS):
        raise ValueError("full original four-camera source required")
    scratch_root = Path(os.environ["TMPDIR"]).resolve()
    if ".runtime-work" not in scratch_root.parts:
        raise ValueError("camera encoding scratch must be under .runtime-work")
    encoded = {}
    for name in CAMERAS:
        source = (root / sources[name]["path"]).resolve()
        target = root / (name + ".mkv")
        if source.parent != root or target.exists() or _sha(source) != sources[name]["sha256"]:
            raise ValueError("original camera source changed or output exists: " + name)
        with tempfile.TemporaryDirectory(dir=scratch_root, prefix="c130282-camera-") as temp:
            scratch = Path(temp)
            with ZipFile(source) as archive:
                members = [f"{row['frame']:08d}.png" for row in rows]
                if archive.namelist() != members:
                    raise ValueError("original camera frame order differs: " + name)
                for index, (row, member) in enumerate(zip(rows, members)):
                    payload = archive.read(member)
                    if row.get("camera_frames", {}).get(name) != {
                            "member": member, "sha256": hashlib.sha256(payload).hexdigest()}:
                        raise ValueError("original camera frame hash differs: " + name)
                    (scratch / f"{index:08d}.png").write_bytes(payload)
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                "-y", "-framerate", "20", "-start_number", "0", "-i",
                str(scratch / "%08d.png"), "-an", "-c:v", "ffv1", "-level", "3",
                str(target)]
            subprocess.run(command, check=True, timeout=1800,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        encoded[name] = {"path": str(target), "sha256": _sha(target),
                         "frame_count": 900, "fps": 20}
    return encoded
