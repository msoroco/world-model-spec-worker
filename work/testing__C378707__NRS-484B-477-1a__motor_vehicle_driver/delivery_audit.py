"""Independent original-source, frame-join, video decode and pixel audit."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

from PIL import Image

from audit_original_attempt import audit as audit_original
from native_acquisition import CAMERAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original frame source missing: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def decode(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original camera video missing: " + path.name)
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1":
        raise ValueError("original camera lossless codec differs")
    count = int(streams[0].get("nb_read_frames", -1))
    full = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
                           "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True)
    if count < 1 or full.returncode:
        raise ValueError("original camera full decode failed")
    return {"sha256": sha(path), "decoded_frames": count,
            "dimensions": [int(streams[0]["width"]), int(streams[0]["height"])],
            "rate": streams[0]["avg_frame_rate"]}


def pixels(video, archive, frame_map, dimensions):
    width, height = dimensions
    size = width * height * 3
    process = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(video),
                                "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with zipfile.ZipFile(archive) as source:
            expected = [f"{index:04d}-{row['native_frame']}.png" for index, row in enumerate(frame_map)]
            if source.namelist() != expected:
                raise ValueError("original camera archive frame order differs")
            for name in expected:
                decoded = process.stdout.read(size)
                if len(decoded) != size:
                    raise ValueError("original camera pixel stream incomplete")
                with Image.open(io.BytesIO(source.read(name))) as image:
                    if image.size != (width, height) or image.convert("RGB").tobytes() != decoded:
                        raise ValueError("original camera source/video pixels differ: " + name)
            if process.stdout.read(1):
                raise ValueError("original camera video contains extra pixels")
        if process.wait(timeout=180) != 0:
            raise ValueError("original camera pixel decoder failed")
        return len(expected)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    planned = json.loads(Path(plan).read_text())
    if case_id not in {item["case_id"] for item in planned["cases"]}:
        raise ValueError("exact delivery case differs")
    source = attempt / "original-attempt"
    original = audit_original(source, case_id)
    count = original["frame_count"]
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    original_map = json.loads((source / "frame-map.json").read_text())["frames"]
    if not all(len(item) == count for item in (mapping, trace, evidence, original_map)):
        raise ValueError("original Core/video/actor frame counts differ")
    for index, (video, source_frame) in enumerate(zip(mapping, original_map)):
        native = source_frame["native_frame"]
        if (video.get("video_frame") != index or video.get("carla_frame") != native or
                abs(video.get("time_s", -1) - source_frame["native_time_s"]) > 1e-4 or
                trace[index].get("frame") != native or evidence[index].get("original_frame") != native):
            raise ValueError("original Core/video/actor frame join differs")
    videos = {view: decode(attempt / (view + ".mkv")) for view in CAMERAS}
    if any(item["decoded_frames"] != count for item in videos.values()):
        raise ValueError("four original cameras have incomplete decode")
    diagnostic = original["diagnostic_fixture"] is True
    verified = {}
    if not diagnostic:
        seal = json.loads((attempt / "capture-seal.json").read_text())
        if seal.get("frames") != count or seal.get("diagnostic_fixture") is not False:
            raise ValueError("original Native capture seal missing")
        for view in CAMERAS:
            verified[view] = pixels(attempt / (view + ".mkv"), source / (view + ".zip"),
                                    original_map, videos[view]["dimensions"])
    return {"format": "c378707-independent-delivery-audit-v1", "case_id": case_id,
            "source_inventory_sha256": sha(source / "inventory.json"),
            "activity_sha256": original["activity_sha256"], "capture_frames": count,
            "four_view_full_decode": videos, "original_pixel_verified_frames": verified,
            "diagnostic_fixture": diagnostic, "actual_pixels_verified": not diagnostic,
            "physical_acceptance": False, "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to replace independent audit")
    outcome = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
