"""Independent source and decode audit of an original NRS 484B.270(2)(a) capture.

This verifies acquisition integrity, not physical visibility, safe lane movement,
due care, legal compliance, or canonical delivery acceptance.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from package_spec import AID, CAMERA_NAMES


def need(ok, message):
    if not ok:
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


def decode_video(path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)], check=True, capture_output=True, text=True)
    need(probe.stdout.strip().isdigit(), "video frame count unavailable: " + path.name)
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                    "-map", "0:v:0", "-f", "null", "-"],
                   check=True, capture_output=True)
    return int(probe.stdout.strip())


def audit(attempt, case_id):
    root = Path(attempt).resolve()
    need(case_id.startswith(AID + "__"), "exact assignment case required")
    receipt_path = source(root, "original-source-receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    need((receipt.get("assignment_id"), receipt.get("case_id")) == (AID, case_id),
         "original receipt case mismatch")
    need(receipt.get("source_kind") == "original_native_capture" and
         receipt.get("diagnostic_fixture") is False and
         receipt.get("physical_acceptance") is False and receipt.get("legal_verdict") is None,
         "original source provenance or acceptance claim invalid")
    count = receipt.get("frame_count")
    need(count == 900 and receipt.get("fps") == 20, "full original 20 Hz capture required")
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
    need(isinstance(receipt.get("reviewed_packet_sha256"), str) and
         len(receipt["reviewed_packet_sha256"]) == 64,
         "reviewed packet source binding missing")
    context = json.loads((root / "original-context.json").read_text(encoding="utf-8"))
    need(context.get("case_id") == case_id, "original context case mismatch")
    trace = rows(root / "original-trace.jsonl")
    mapping = rows(root / "camera-frame-map.jsonl")
    canonical_mapping = rows(root / "video_frames.jsonl")
    canonical_trace = rows(root / "trace.jsonl")
    need(len(trace) == len(mapping) == len(canonical_mapping) == len(canonical_trace) == count,
         "original trace/camera frame count mismatch")
    previous = None
    for index, (actor, cameras) in enumerate(zip(trace, mapping)):
        frame, time_s = actor.get("frame"), actor.get("time_s")
        need(type(frame) is int and type(time_s) in (int, float) and math.isfinite(time_s),
             "original actor frame identity missing")
        need(cameras.get("frame") == frame and cameras.get("time_s") == time_s,
             "original camera/actor frame join mismatch")
        canonical = canonical_mapping[index]
        derived = canonical_trace[index]
        need(canonical.get("video_frame") == index and canonical.get("carla_frame") == frame and
             canonical.get("native_frame") == frame and canonical.get("time_s") == time_s and
             canonical.get("camera_png_sha256") == cameras.get("camera_png_sha256") and
             derived.get("frame") == frame and derived.get("time_s") == time_s and
             derived.get("ego_lane_id") == actor.get("ego_lane_id") and
             derived.get("control_lane_id") == actor.get("control_lane_id"),
             "canonical original frame or trace join mismatch")
        if previous is not None:
            need(frame == previous[0] + 1 and abs(time_s - previous[1] - .05) <= .002,
                 "original 20 Hz frame sequence mismatch")
        previous = frame, time_s
        pixel_hashes = cameras.get("camera_png_sha256")
        need(isinstance(pixel_hashes, dict) and set(pixel_hashes) == set(CAMERA_NAMES) and
             all(isinstance(v, str) and len(v) == 64 for v in pixel_hashes.values()),
             "four original camera pixel hashes required")
    cameras = receipt.get("cameras")
    need(isinstance(cameras, dict) and set(cameras) == set(CAMERA_NAMES),
         "four original camera files required")
    for name in CAMERA_NAMES:
        info = cameras[name]
        need(info.get("path") == name + ".mkv" and info.get("frame_count") == count,
             "camera file identity or declared frame count mismatch: " + name)
        path = source(root, info["path"])
        digest = sha(path)
        need(digest == info.get("sha256"), "original camera bytes changed: " + name)
        need(decode_video(path) == count, "full original video decode/frame count failed: " + name)
        bindings[path.name] = digest
    return {"format": "pass-original-capture-audit", "assignment_id": AID,
            "case_id": case_id, "receipt_sha256": sha(receipt_path),
            "frame_count": count, "full_decode": True, "source_bindings": bindings,
            "physical_visibility_confirmed": False, "legal_verdict": None,
            "canonical_delivery_acceptance": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise ValueError("retain prior audit; choose a fresh output")
    arguments.output.write_text(json.dumps(audit(arguments.attempt, arguments.case), indent=2) + "\n",
                                encoding="utf-8")
