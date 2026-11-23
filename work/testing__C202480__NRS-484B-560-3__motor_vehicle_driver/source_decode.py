"""Decode all four original videos with the pinned runtime media auditor.

Nonuniform sampled pixels are a source quality check. They do not establish
visibility of the crossing device, markings, vehicles, or legal compliance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from native_camera import VIEWS
from owner_release import verify_release


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned_auditor():
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    path = Path(output).resolve() if output else None
    private = next((parent for parent in (path, *path.parents)
                    if parent.name == ".runtime-work"), None) if path else None
    if private is None:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    root = private.parent
    sys.path.insert(0, str(root / "runtime"))
    from scenario_pipeline.worker_exchange.media import audit
    return audit


def _probe(video: Path, width: int, height: int) -> None:
    completed = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-of", "json", str(video)], capture_output=True, text=True, check=True)
    streams = json.loads(completed.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
            streams[0].get("width") != width or
            streams[0].get("height") != height or
            streams[0].get("r_frame_rate") != "20/1"):
        raise ValueError("original video codec, dimensions or rate differs")


def _nonuniform(frame) -> None:
    pixels = frame.pixels
    if not pixels:
        raise ValueError("decoded original camera frame has no pixels")
    sample = pixels[::max(1, len(pixels) // 4096)]
    if min(sample) == max(sample):
        raise ValueError("decoded original camera frame is sampled-uniform")


def decode_one(video: Path, receipt_path: Path, mapping_hash: str,
               count: int, dimensions: tuple[int, int], *, auditor=None) -> dict:
    video, receipt_path = Path(video).resolve(), Path(receipt_path).resolve()
    _probe(video, *dimensions)
    run = auditor or _pinned_auditor()
    version = sha(Path(__file__).resolve())
    result = run(video, count,
                 checkers={"nonuniform_camera_samples_v1": (version, _nonuniform)},
                 mapping_sha256=mapping_hash, receipt=receipt_path)
    if (result.get("frames") != count or result.get("dimensions") != list(dimensions) or
            result.get("video_sha256") != sha(video) or
            result.get("mapping_sha256") != mapping_hash or
            result.get("checks", {}).get("nonuniform_camera_samples_v1") != version):
        raise ValueError("pinned complete source decode receipt differs")
    return result


def audit_four_sources(attempt: Path) -> dict:
    attempt = Path(attempt).resolve()
    if not any(parent.name == ".runtime-work" for parent in attempt.parents):
        raise ValueError("source decode requires private original attempt")
    verify_release(attempt)
    media = json.loads((attempt / "media-receipt.json").read_text(encoding="utf-8"))
    mapping = attempt / "video_frames.jsonl"
    mapping_hash = sha(mapping)
    if (media.get("format") != "c202480-original-four-camera-media-v1" or
            media.get("frames") != 900 or
            media.get("frame_map_sha256") != mapping_hash or
            set(media.get("video_sha256", {})) != {name for name, _, _ in VIEWS}):
        raise ValueError("original media receipt or frame map differs")
    if (attempt / "source-decode-receipt.json").exists():
        raise ValueError("retain previous source decode receipt")
    receipts = {}
    for name, width, height in VIEWS:
        video = attempt / (name + ".mkv")
        if sha(video) != media["video_sha256"][name]:
            raise ValueError("original camera video hash differs")
        path = attempt / ("source-decode-" + name + ".json")
        decode_one(video, path, mapping_hash, 900, (width, height))
        receipts[name] = {"path": path.name, "sha256": sha(path)}
    result = {"format": "c202480-four-original-source-decode-v1",
              "frames": 900, "frame_map_sha256": mapping_hash,
              "media_receipt_sha256": sha(attempt / "media-receipt.json"),
              "receipts": receipts, "sampled_pixels_nonuniform": True,
              "feature_visibility_verified": False,
              "physical_acceptance_claimed": False}
    (attempt / "source-decode-receipt.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_four_sources(args.attempt), indent=2))
