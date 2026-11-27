"""Encode and verify four original taxi camera streams after Native release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from native_taxi_operator import SIZES
from taxi_stand_measurement import VIEWS


def encode_views(original_frames: Path, destination: Path) -> dict:
    original_frames = Path(original_frames)
    destination = Path(destination)
    ledger = json.loads((original_frames / "native_frames.json").read_text())
    if not isinstance(ledger, list) or len(ledger) != 900:
        raise ValueError("original taxi camera frame ledger is incomplete")
    if destination.exists():
        raise ValueError("retain prior taxi camera encodes")
    destination.mkdir(parents=True)
    outputs = {}
    for name in VIEWS:
        folder = original_frames / name
        frames = sorted(folder.glob("*.png"))
        if len(frames) != 900 or [path.name for path in frames] != [f"{i:04d}.png" for i in range(900)]:
            raise ValueError("original taxi camera stream lacks 900 ordered frames: " + name)
        for index, frame in enumerate(frames):
            record = ledger[index]
            source = record.get("cameras", {}).get(name, {})
            if (record.get("frame") != index
                    or source.get("path") != str(frame.relative_to(original_frames))
                    or hashlib.sha256(frame.read_bytes()).hexdigest() != source.get("sha256")):
                raise ValueError("original taxi camera frame SHA-256 differs: " + name)
        target = destination / ("raw.mkv" if name == "overview" else name + ".mkv")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-framerate", "20", "-i", str(folder / "%04d.png"),
                   "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                   "-pix_fmt", "yuv420p", str(target)]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,nb_read_frames,r_frame_rate",
                                "-of", "json", str(target)],
                               check=True, capture_output=True, text=True, timeout=60)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1:
            raise ValueError("taxi camera video stream count differs: " + name)
        stream = streams[0]
        width, height = SIZES[name]
        if (stream.get("width") != width or stream.get("height") != height
                or stream.get("r_frame_rate") != "20/1"
                or int(stream.get("nb_read_frames", -1)) != 900):
            raise ValueError("taxi camera encoded video differs from original plan: " + name)
        outputs[name] = {"path": str(target.name),
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                         "width": width, "height": height,
                         "frames": 900, "rate_hz": 20}
    (destination / "camera-encodes.json").write_text(json.dumps(outputs, indent=2, sort_keys=True) + "\n")
    return outputs
