"""Verify and encode original four-view Native pixels after acquisition."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_camera import VIEWS


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private(attempt: Path) -> Path:
    root = Path(__file__).resolve().parents[2] / ".runtime-work"
    attempt = Path(attempt).resolve()
    if root not in attempt.parents:
        raise ValueError("original media must stay under .runtime-work")
    return attempt


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("original trace or frame map missing")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def validate_sources(attempt: Path, *, count: int = 900, views=VIEWS) -> tuple[dict, dict]:
    """Require one complete source-bound trace, frame map and raw pixel set."""
    attempt = _private(attempt)
    trace = _rows(attempt / "trace.jsonl")
    mapping = _rows(attempt / "video_frames.jsonl")
    if len(trace) != count or len(mapping) != count or count < 1:
        raise ValueError("original trace/frame map duration differs")
    files = {name: [] for name, _, _ in views}
    source_hash = trace[0].get("source_packet_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("original source packet hash missing")
    previous = None
    for index, (row, mapped) in enumerate(zip(trace, mapping)):
        frame, time_s = row.get("frame"), row.get("time_s")
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not math.isfinite(time_s) or row.get("source_frame") != frame or
                row.get("source_packet_sha256") != source_hash or
                row.get("physical_acceptance_claimed") is not False or
                (previous is not None and (frame != previous[0] + 1 or
                                           not .049 <= time_s - previous[1] <= .051))):
            raise ValueError("original Native trace identity or cadence differs")
        previous = (frame, time_s)
        cameras = row.get("camera_sources")
        hashes = mapped.get("camera_source_sha256")
        if (not isinstance(cameras, dict) or set(cameras) != set(files) or
                not isinstance(hashes, dict) or set(hashes) != set(files) or
                mapped.get("video_frame") != index or mapped.get("carla_frame") != frame or
                mapped.get("native_frame") != frame or mapped.get("time_s") != time_s):
            raise ValueError("original camera/frame map join differs")
        for name, width, height in views:
            item = cameras[name]
            relative = item.get("raw_bgra") if isinstance(item, dict) else None
            if (not isinstance(relative, str) or item.get("frame") != frame or
                    item.get("width") != width or item.get("height") != height or
                    type(item.get("time_s")) not in (int, float) or
                    abs(item["time_s"] - time_s) > .05 or
                    hashes[name] != item.get("sha256")):
                raise ValueError("original camera source identity differs")
            raw_root = (attempt / "raw").resolve()
            raw = (raw_root / relative).resolve()
            if (raw_root not in raw.parents or not raw.is_file() or
                    raw.stat().st_size != width * height * 4 or sha(raw) != item["sha256"]):
                raise ValueError("original camera pixel source differs")
            files[name].append(raw)
    return {"frames": count, "source_packet_sha256": source_hash,
            "trace_sha256": sha(attempt / "trace.jsonl"),
            "frame_map_sha256": sha(attempt / "video_frames.jsonl")}, files


def encode(files: list[Path], width: int, height: int, destination: Path) -> None:
    """Feed validated BGRA bytes into lossless FFV1 without generated pixels."""
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
               "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
               "-framerate", "20", "-i", "pipe:0", "-frames:v", str(len(files)),
               "-an", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgra", str(destination)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    try:
        for path in files:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    process.stdin.write(chunk)
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError("lossless camera encode failed: " + error.decode("utf-8", "replace")[-1000:])
    except Exception:
        process.kill()
        process.wait()
        destination.unlink(missing_ok=True)
        raise
    finally:
        process.stderr.close()
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError("lossless camera output missing")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,nb_read_frames", "-of", "json",
                            str(destination)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
            streams[0].get("width") != width or streams[0].get("height") != height or
            streams[0].get("nb_read_frames") != str(len(files))):
        destination.unlink(missing_ok=True)
        raise ValueError("lossless camera frame count, dimensions or codec differ")


def finalize(attempt: Path) -> dict:
    """Keep four videos and a receipt beside the original, immutable frame map."""
    attempt = _private(attempt)
    targets = [attempt / (name + ".mkv") for name, _, _ in VIEWS]
    targets.append(attempt / "media-receipt.json")
    if any(target.exists() for target in targets):
        raise ValueError("retain previous original media")
    receipt, files = validate_sources(attempt)
    videos = {}
    for name, width, height in VIEWS:
        target = attempt / (name + ".mkv")
        encode(files[name], width, height, target)
        videos[name] = sha(target)
    receipt.update(format="c179789-original-four-camera-media-v1",
                   video_sha256=videos, physical_acceptance_claimed=False,
                   pixel_visibility_verified=False)
    (attempt / "media-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                                encoding="utf-8")
    return receipt
