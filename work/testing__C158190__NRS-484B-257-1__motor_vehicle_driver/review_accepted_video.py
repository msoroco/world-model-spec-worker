"""Decode all frames of a frozen accepted recording after source admission.

This establishes byte-bound decode integrity, not visible traffic, control,
stopping behavior, or legal coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from accepted_source import SourceError, sha, verify


def review_video(repo: Path, recording_id: str, trace: Path, video: Path) -> dict:
    admitted = verify(repo, recording_id, trace, video)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(video)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1:
            raise SourceError("one original video stream required")
        stream = streams[0]
        width, height = stream.get("width"), stream.get("height")
        if (type(width) is not int or type(height) is not int or
                width <= 0 or height <= 0 or stream.get("r_frame_rate") != "20/1"):
            raise SourceError("original video dimensions or rate differ")
        decoded = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "4",
             "-i", str(video), "-map", "0:v:0", "-vsync", "0", "-f", "framemd5", "pipe:1"],
            check=True, capture_output=True, text=True, timeout=3600,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as exc:
        raise SourceError("original video full decode failed") from exc
    rows = [line for line in decoded.stdout.splitlines() if line and not line.startswith("#")]
    if len(rows) != admitted["frames_declared"]:
        raise SourceError("original video decoded frame count differs")
    if any(len(row.split(",")) < 6 for row in rows):
        raise SourceError("original video frame digest is incomplete")
    if sha(video) != admitted["video_sha256"]:
        raise SourceError("original video changed during decode")
    return {
        "format": "accepted-original-video-decode-review",
        "assignment_id": admitted["assignment_id"],
        "recording_id": recording_id,
        "case_id": admitted["case_id"],
        "video_sha256": admitted["video_sha256"],
        "decoded_frames": len(rows),
        "width": width,
        "height": height,
        "frame_rate": stream["r_frame_rate"],
        "frame_digest_sequence_sha256": hashlib.sha256(
            ("\n".join(rows) + "\n").encode("utf-8")
        ).hexdigest(),
        "finding": "All original video frames decoded; physical pixel visibility and legal coverage require independent review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review_video(args.repo.resolve(), args.recording_id,
                                  args.trace, args.video), sort_keys=True))


if __name__ == "__main__":
    main()
