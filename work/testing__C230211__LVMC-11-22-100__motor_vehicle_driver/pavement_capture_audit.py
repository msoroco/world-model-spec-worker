"""Independent original source/frame/video audit for a pavement attempt."""

import hashlib
import json
from pathlib import Path
import subprocess

from package_spec import CAMERA_NAMES


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def decode(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries", "stream=nb_read_frames",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                           check=True, text=True, capture_output=True)
    need(probe.stdout.strip() == "900", "original camera frame count differs")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                    "-f", "null", "-"], check=True, capture_output=True)


def audit(attempt, case):
    attempt = Path(attempt).resolve()
    receipt_path = attempt / "original-source-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    need(receipt.get("source_kind") == "original_native_capture" and
         receipt.get("diagnostic_fixture") is False and
         receipt.get("case_id") == case and receipt.get("fps") == 20 and
         receipt.get("frame_count") == 900, "original Native pavement receipt differs")
    files = {"pavement-packet.json": "packet_sha256",
             "trace.jsonl": "trace_sha256",
             "video_frames.jsonl": "frame_map_sha256",
             "pavement-measurement.json": "measurement_sha256"}
    for name, key in files.items():
        path = attempt / name
        need(path.is_file() and sha(path) == receipt.get(key),
             "original pavement source hash differs: " + name)
    packet = json.loads((attempt / "pavement-packet.json").read_text())
    trace = rows(attempt / "trace.jsonl")
    frames = rows(attempt / "video_frames.jsonl")
    need(packet.get("case_id") == case and len(packet.get("frames", [])) ==
         len(trace) == len(frames) == 900, "original pavement frame history incomplete")
    previous = None
    for index, (body, motion, mapped) in enumerate(zip(packet["frames"], trace, frames)):
        frame = body.get("frame")
        time_s = body.get("time_s")
        need(mapped.get("video_frame") == index and
             mapped.get("carla_frame") == mapped.get("native_frame") ==
             motion.get("frame") == frame and
             mapped.get("time_s") == motion.get("time_s") == time_s and
             len(body.get("vehicle_position_xy", [])) == 2 and
             body.get("vehicle_position_xy") == motion.get("position_m", [])[:2] and
             bool(body.get("warning_actor_ids")) and
             body.get("reviewed_site_sha256") == packet.get("reviewed_site_sha256") and
             body.get("protection") == packet.get("scene", {}).get("protection"),
             "original pavement body/frame join differs")
        if previous is not None:
            need(frame == previous[0] + 1 and abs(time_s - previous[1] - .05) <= .002,
                 "original barrier frame cadence differs")
        previous = frame, time_s
    cameras = receipt.get("cameras")
    need(isinstance(cameras, dict) and set(cameras) == set(CAMERA_NAMES),
         "four original pavement videos missing")
    for name, ref in cameras.items():
        path = (attempt / ref["path"]).resolve()
        need(path.parent == attempt and path.is_file() and
             sha(path) == ref["sha256"] and ref.get("frame_count") == 900,
             "original pavement video hash differs: " + name)
        decode(path)
    return {"format": "pavement-original-source-audit", "case_id": case,
            "receipt_sha256": sha(receipt_path), "frame_count": 900,
            "full_decode": True, "actual_pixels_reviewed": False,
            "source_verified": True, "legal_verdict": None}
