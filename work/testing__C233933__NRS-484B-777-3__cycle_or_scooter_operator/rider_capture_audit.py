"""Independently verify original rider-formation source joins and full camera decode."""

import hashlib
import json
from pathlib import Path
import subprocess

from package_spec import CAMERA_NAMES


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def decode(path):
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout)
    stream = info["streams"][0]
    need(stream.get("nb_frames") == "900" and stream.get("r_frame_rate") == "20/1",
         "original camera frame rate/count differs")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                    "-f", "null", "-"], check=True, capture_output=True)


def audit(attempt, case):
    attempt = Path(attempt).resolve()
    receipt_path = attempt / "original-source-receipt.json"
    need(receipt_path.is_file(), "original rider-formation source receipt missing")
    receipt = json.loads(receipt_path.read_text())
    need(receipt.get("source_kind") == "original_native_capture" and
         receipt.get("diagnostic_fixture") is False and
         receipt.get("case_id") == case and receipt.get("fps") == 20 and
         receipt.get("frame_count") == 900, "original source receipt differs")
    for name, key in (("rider-history.json", "history_sha256"),
                      ("trace.jsonl", "trace_sha256"),
                      ("video_frames.jsonl", "frame_map_sha256"),
                      ("rider-measurement.json", "measurement_sha256")):
        path = attempt / name
        need(path.is_file() and sha(path) == receipt.get(key),
             "original rider-formation source hash differs: " + name)
    history = json.loads((attempt / "rider-history.json").read_text())
    trace = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    need(history.get("case_id") == case and len(history.get("samples", ())) ==
         len(trace) == len(mapping) == 900, "original whole maneuver incomplete")
    from abreast import CASES, SOURCES, validate_scene
    exact = next((item for item in CASES if case.endswith('__' + item.name)), None)
    need(exact is not None, 'unknown exact rider case')
    scene = history['scene']
    validate_scene(scene, exact)
    need(len(history['native_actor_ids']) == exact.riders and
         len(set(history['native_actor_ids'])) == exact.riders,
         'separate original rider identities missing')
    prior = None
    for i, (body, motion, frame) in enumerate(zip(history["samples"], trace, mapping)):
        need(body.get("frame") == frame.get("video_frame") == i and
             body.get("native_frame") == motion.get("frame") ==
             frame.get("native_frame") == frame.get("carla_frame") and
             body.get("time_s") == motion.get("time_s") == frame.get("time_s") and
             body.get("native_actor_ids") == history.get("native_actor_ids") and
             body.get("rider_ids") == scene.get("rider_ids") and
             all(body.get(name + "_source_sha256") == scene.get(name + "_source_sha256") for name in SOURCES),
             "original actor/trace/video frame join differs")
        if prior is not None:
            need(frame["native_frame"] == prior[0] + 1 and
                 abs(frame["time_s"] - prior[1] - .05) <= .002,
                 "original rider-formation frame cadence differs")
        prior = frame["native_frame"], frame["time_s"]
    cameras = receipt.get("cameras")
    need(isinstance(cameras, dict) and set(cameras) == set(CAMERA_NAMES),
         "four original cameras missing")
    for name, ref in cameras.items():
        path = (attempt / ref["path"]).resolve()
        need(path.parent == attempt and path.is_file() and sha(path) == ref["sha256"] and
             ref.get("frame_count") == 900, "original camera hash differs: " + name)
        decode(path)
    return {"format": "rider-formation-original-source-audit", "case_id": case,
            "receipt_sha256": sha(receipt_path), "frame_count": 900,
            "full_decode": True, "actual_pixels_reviewed": False,
            "source_verified": True, "legal_verdict": None}
