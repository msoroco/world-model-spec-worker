"""Decode sealed original PNG archives into four derived FFV1 camera videos.

The archives remain untouched. Call only in a fresh saved-processing stage.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from camera_sources import CAMERAS, audit_camera_sources


def prepare(stage: Path, *, diagnostic_fixture: bool = False,
            reuse_existing: bool = False) -> dict:
    root = Path(stage)
    audited = audit_camera_sources(root, diagnostic_fixture=diagnostic_fixture)
    manifest = json.loads((root / "nearest-view-camera-manifest.json").read_text())
    rows = manifest["rows"]
    outputs = {}
    existing = {name for name in CAMERAS if (root / (name + ".mkv")).exists()}
    if existing and (not reuse_existing or existing != set(CAMERAS)):
        raise ValueError("derived camera video already exists or source set incomplete")
    for name in CAMERAS:
        target = root / (name + ".mkv")
        source = root / manifest["sources"][name]["path"]
        if not existing:
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                   "-f", "image2pipe", "-vcodec", "png", "-framerate", "20",
                   "-i", "pipe:0", "-an", "-c:v", "ffv1", "-pix_fmt", "rgb24",
                   str(target)]
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with ZipFile(source) as archive:
                    for row in rows:
                        process.stdin.write(archive.read(f"{row['frame']:08d}.png"))
                process.stdin.close()
                error = process.stderr.read().decode(errors="replace")
                if process.wait() != 0:
                    raise ValueError("derived camera encode failed: " + error[-500:])
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                if target.exists():
                    target.unlink()
                raise
            finally:
                process.stderr.close()
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames", "-of", "default=noprint_wrappers=1:nokey=1",
                                str(target)], capture_output=True, text=True, check=True)
        if int(probe.stdout.strip()) != len(rows):
            target.unlink()
            raise ValueError("derived camera frame count differs: " + name)
        outputs[name] = {"path": target.name, "frames": len(rows),
                         "source_archive": source.name}
    return {"format": "c158208-derived-camera-videos-v1", "original_camera_audit": audited,
            "videos": outputs, "legal_status": "unresolved", "physical_acceptance": False}
