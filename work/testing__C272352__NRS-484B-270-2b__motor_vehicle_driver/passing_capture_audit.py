"""Independent original Native source and full video decode audit."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


AID = "testing__C272352__NRS-484B-270-2b__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    need(path.is_file() and not path.is_symlink() and path.resolve().parent == root,
         "missing original source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def decode(video):
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                             "-select_streams", "v:0", "-show_entries",
                             "stream=nb_read_frames", "-of",
                             "default=noprint_wrappers=1:nokey=1", str(video)],
                            check=True, capture_output=True, text=True)
    need(result.stdout.strip().isdigit(), "video frame count unavailable")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video),
                    "-map", "0:v:0", "-f", "null", "-"],
                   check=True, capture_output=True)
    return int(result.stdout.strip())


def audit(attempt, case_id):
    root = Path(attempt).resolve()
    need(case_id.startswith(AID + "__"), "exact assignment case required")
    receipt_path = source(root, "original-source-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    need(receipt.get("case_id") == case_id and
         receipt.get("source_kind") == "original_native_capture" and
         receipt.get("diagnostic_fixture") is False and
         receipt.get("physical_acceptance") is False and
         receipt.get("legal_verdict") is None,
         "original Native provenance/acceptance scope invalid")
    count = receipt.get("frame_count")
    need(count == 900 and receipt.get("fps") == 20,
         "full original 900-frame capture required")
    bindings = {}
    for name, field in (("original-context.json", "context_sha256"),
                        ("original-trace.jsonl", "trace_sha256"),
                        ("camera-frame-map.jsonl", "frame_map_sha256"),
                        ("video_frames.jsonl", "canonical_frame_map_sha256"),
                        ("trace.jsonl", "canonical_trace_sha256")):
        path = source(root, name)
        digest = sha(path)
        need(digest == receipt.get(field), "original source changed: " + name)
        bindings[name] = digest
    context = json.loads(source(root, "original-context.json").read_text())
    need(context.get("case_id") == case_id and
         context.get("reviewed_packet_sha256") == receipt.get("reviewed_packet_sha256"),
         "reviewed Native site context mismatch")
    trace = rows(root / "original-trace.jsonl")
    camera_map = rows(root / "camera-frame-map.jsonl")
    canonical = rows(root / "video_frames.jsonl")
    motion = rows(root / "trace.jsonl")
    need(len(trace) == len(camera_map) == len(canonical) == len(motion) == count,
         "original trace/camera count mismatch")
    prior = None
    for index, (actor, camera, frame_map, motion_row) in enumerate(
            zip(trace, camera_map, canonical, motion)):
        frame, time_s = actor.get("frame"), actor.get("time_s")
        need(type(frame) is int and type(time_s) in (int, float) and
             math.isfinite(time_s), "original actor frame/time missing")
        need(camera.get("frame") == frame and camera.get("time_s") == time_s and
             frame_map.get("video_frame") == index and
             frame_map.get("carla_frame") == frame and
             frame_map.get("native_frame") == frame and
             frame_map.get("time_s") == time_s and
             frame_map.get("camera_png_sha256") == camera.get("camera_png_sha256") and
             motion_row.get("frame") == frame and motion_row.get("time_s") == time_s,
             "original camera/actor canonical frame join mismatch")
        if prior is not None:
            need(frame == prior[0] + 1 and abs(time_s - prior[1] - .05) <= .002,
                 "original 20 Hz sequence mismatch")
        prior = (frame, time_s)
        hashes = camera.get("camera_png_sha256")
        need(isinstance(hashes, dict) and set(hashes) == set(CAMERAS) and
             all(isinstance(value, str) and len(value) == 64 for value in hashes.values()),
             "four original camera source hashes required")
    videos = receipt.get("cameras")
    need(isinstance(videos, dict) and set(videos) == set(CAMERAS),
         "four original camera files required")
    for name in CAMERAS:
        info = videos[name]
        need(info.get("path") == name + ".mkv" and info.get("frame_count") == count,
             "original camera identity/count mismatch: " + name)
        path = source(root, info["path"])
        need(sha(path) == info.get("sha256"), "original video bytes changed: " + name)
        need(decode(path) == count, "full original video decode failed: " + name)
        bindings[path.name] = sha(path)
    return {"format": "passing-original-capture-audit", "assignment_id": AID,
            "case_id": case_id, "receipt_sha256": sha(receipt_path),
            "frame_count": count, "full_decode": True,
            "source_bindings": bindings, "physical_visibility_confirmed": False,
            "canonical_acceptance": False, "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior audit")
    args.output.write_text(json.dumps(audit(args.attempt, args.case), indent=2) + "\n",
                           encoding="utf-8")
