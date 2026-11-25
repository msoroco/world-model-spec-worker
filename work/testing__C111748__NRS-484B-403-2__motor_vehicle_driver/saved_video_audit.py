"""Decode every saved camera frame for one source-sealed device-duty attempt."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("device_source_audit_for_video", ROOT / "saved_delivery.py")
_sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sources)

PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
LOSSLESS = {"ffv1", "png", "huffyuv", "rawvideo"}


class VideoAuditError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise VideoAuditError(message)


def command(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise VideoAuditError(f"video tool or full decode failed: {exc}") from exc


def decode(path: Path, *, size: tuple[int, int], frames: int = 900) -> dict:
    """Probe the stream and force a complete FFmpeg frame-by-frame decode."""
    probe = json.loads(command(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=codec_name,width,height,avg_frame_rate,time_base",
                                "-of", "json", str(path)]))
    streams = probe.get("streams", [])
    require(len(streams) == 1, "one video stream required")
    stream = streams[0]
    require(stream.get("codec_name") in LOSSLESS, "lossless camera encoding required")
    require((stream.get("width"), stream.get("height")) == tuple(size), "camera profile dimensions differ")
    require(stream.get("avg_frame_rate") in ("20/1", "20"), "camera cadence differs from 20 Hz")
    digest_lines = command(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                            "-map", "0:v:0", "-an", "-sn", "-dn", "-f", "framemd5", "-"])
    rows = [line for line in digest_lines.splitlines() if line and not line.startswith("#")]
    require(len(rows) == frames, "full decode frame count differs from Native")
    timestamps = []
    digest = hashlib.sha256()
    for row in rows:
        fields = [part.strip() for part in row.split(",")]
        require(len(fields) == 6 and len(fields[5]) == 32, "invalid decoded frame digest")
        try:
            timestamps.append((int(fields[2]), int(fields[3])))
        except ValueError as exc:
            raise VideoAuditError("invalid decoded frame timestamp") from exc
        digest.update((row + "\n").encode())
    require(all(duration == 1 for _, duration in timestamps), "decoded frame duration differs")
    require(all(timestamps[i][0] == timestamps[0][0] + i for i in range(len(timestamps))),
            "decoded frames are not contiguous")
    return {"codec": stream["codec_name"], "dimensions": list(size),
            "frame_count": len(rows), "decoded_frames_sha256": digest.hexdigest()}


def audit(attempt: Path, *, case_id: str, profile: dict | None = None,
          expected_frames: int = 900, diagnostic_allowed: bool = False) -> dict:
    """Join four decoded streams to an independently checked Native attempt."""
    source = _sources.audit(attempt, case_id=case_id,
                            diagnostic_allowed=diagnostic_allowed)
    require(source["frame_count"] == expected_frames, "Native and video frame counts differ")
    root = attempt.resolve()
    manifest = json.loads((root / "saved-sources.json").read_text(encoding="utf-8"))
    dimensions = PROFILE if profile is None else profile
    require(set(dimensions) == set(PROFILE), "four-camera profile missing")
    decoded = {}
    for name in PROFILE:
        path = (root / manifest["media"][name]["path"]).resolve()
        require(path.is_relative_to(root), "video escapes attempt")
        decoded[name] = decode(path, size=dimensions[name], frames=expected_frames)
    return {**source, "full_video_decode": True, "decoded_media": decoded,
            "actual_pixels": False, "physical_completion": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit(args.attempt, case_id=args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
