"""Independently verify original approach/turn joins and full camera decode."""

import hashlib
import json
from pathlib import Path
import subprocess

from package_spec import CAMERA_NAMES
from turn_position import measure


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
    need(receipt_path.is_file(), "original turn-position source receipt missing")
    receipt = json.loads(receipt_path.read_text())
    need(receipt.get("source_kind") == "original_native_capture" and
         receipt.get("diagnostic_fixture") is False and
         receipt.get("case_id") == case and receipt.get("fps") == 20 and
         receipt.get("frame_count") == 900, "original source receipt differs")
    for name, key in (("turn-position-history.json", "history_sha256"),
                      ("trace.jsonl", "trace_sha256"),
                      ("video_frames.jsonl", "frame_map_sha256"),
                      ("turn-position-measurement.json", "measurement_sha256")):
        path = attempt / name
        need(path.is_file() and sha(path) == receipt.get(key),
             "original turn-position source hash differs: " + name)
    history = json.loads((attempt / "turn-position-history.json").read_text())
    trace = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    need(history.get("case_id") == case and len(history.get("samples", ())) ==
         len(trace) == len(mapping) == 900, "original turn-position interval incomplete")
    need(history.get("public_highway") is True and
         history.get("non_alley_intersection") is True and
         history.get("t_intersection") is True and
         history.get("connected_right_exit") is True and
         type(history.get("right_turn_lane_qualified_under_223_4")) is bool and
         history.get("driver_actor_id") and history.get("public_highway_source") and
         history.get("intersection_source") and history.get("right_lane_design_source") and
         history.get("qualification_223_4_source") and history.get("connected_right_exit_source") and
         history.get("turn_phase_lane_source") and history.get("turn_phase_lane_refs") and
         history.get("intended_maneuver", {}).get("source_ref"),
         "independent highway, lane qualification or intention source missing")
    prior = None
    for i, (body, motion, frame) in enumerate(zip(history["samples"], trace, mapping)):
        need(body.get("frame") == frame.get("video_frame") == i and
             body.get("native_frame") == motion.get("frame") ==
             frame.get("native_frame") == frame.get("carla_frame") and
             body.get("time_s") == motion.get("time_s") == frame.get("time_s") and
             body.get("actor_ids") == history.get("actor_ids") and
             abs(body["speed_mps"] - motion["speed_mps"]) < 1e-6 and
             body.get("driver_id") == history.get("driver_actor_id"),
             "original vehicle/trace/video frame join differs")
        if prior is not None:
            need(frame["native_frame"] == prior[0] + 1 and
                 abs(frame["time_s"] - prior[1] - .05) <= .002,
                 "original turn-position frame cadence differs")
        prior = frame["native_frame"], frame["time_s"]
    site = {key: history[key] for key in
            ("map_sha256", "public_highway_source", "intersection_source",
             "right_lane_design_source", "qualification_223_4_source",
             "connected_right_exit_source", "turn_phase_lane_source",
             "turn_phase_lane_refs", "driver_identity_source", "entry_road_id",
             "right_exit_road_id", "junction_id", "turn_lane_id", "extreme_right_lane_id",
             "public_highway", "non_alley_intersection", "t_intersection",
             "connected_right_exit", "right_turn_lane_qualified_under_223_4")}
    site["source_id"] = history["reviewed_site_sha256"]
    site["driver_id"] = history["driver_actor_id"]
    original = [{key: row[key] for key in
                 ("original_frame", "time_s", "driver_id", "road_id", "lane_id",
                  "junction_id", "phase", "source_ref", "position_xyz_m")}
                for row in history["samples"]]
    need(json.loads((attempt / "turn-position-measurement.json").read_text()) ==
         measure(site, original, history["intended_maneuver"]),
         "original measured approach/turn intervals differ")
    cameras = receipt.get("cameras")
    need(isinstance(cameras, dict) and set(cameras) == set(CAMERA_NAMES),
         "four original cameras missing")
    for name, ref in cameras.items():
        path = (attempt / ref["path"]).resolve()
        need(path.parent == attempt and path.is_file() and sha(path) == ref["sha256"] and
             ref.get("frame_count") == 900, "original camera hash differs: " + name)
        decode(path)
    return {"format": "turn-position-original-source-audit", "case_id": case,
            "receipt_sha256": sha(receipt_path), "frame_count": 900,
            "full_decode": True, "actual_pixels_reviewed": False,
            "source_verified": True, "legal_verdict": None}
