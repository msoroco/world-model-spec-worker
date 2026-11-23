"""Finalize one saved right-turn attempt from retained original sources."""

import hashlib
import json
import subprocess
from pathlib import Path

from native_sources import CAMERAS, RATE_HZ
from turn_signal_measurements import analyze


def _probe(path):
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True)
    if process.returncode:
        raise ValueError("Original camera decode failed: " + path.name)
    streams = json.loads(process.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("Single original camera stream required: " + path.name)
    return streams[0]


def _signed_turn(heading, baseline):
    return (heading - baseline + 180) % 360 - 180


def _validate_course(root, context):
    rows = [json.loads(line) for line in (root / "drive_history.jsonl").read_text().splitlines()
            if line.strip()]
    if len(rows) < 3:
        raise ValueError("Incomplete original course history")
    baseline = rows[0].get("ego_heading_deg")
    if type(baseline) not in (int, float):
        raise ValueError("Missing original Native heading")
    if (rows[0].get("ego_road_id"), rows[0].get("ego_lane_id")) != (
            context["approach_road_id"], context["approach_lane_id"]):
        raise ValueError("Original trace does not begin on sourced approach")
    onset = next((row["frame"] for row in rows
                  if type(row.get("ego_heading_deg")) in (int, float) and
                  _signed_turn(row["ego_heading_deg"], baseline) <= -5), None)
    if onset != context["turn_onset_frame"]:
        raise ValueError("Turn onset differs from original heading trace")
    final = rows[-1]
    if (final.get("ego_road_id"), final.get("ego_lane_id")) != (
            context["outgoing_road_id"], context["outgoing_lane_id"]):
        raise ValueError("Original trace does not reach sourced outgoing lane")
    angle = _signed_turn(final.get("ego_heading_deg", 0), baseline)
    if not -150 < angle < -30:
        raise ValueError("Original heading trace is not a completed right turn")
    return {"turn_onset_frame": onset, "final_heading_change_degrees": angle,
            "outgoing_road_id": final["ego_road_id"],
            "outgoing_lane_id": final["ego_lane_id"]}


def finalize(root):
    root = Path(root)
    result = analyze(root)
    context = json.loads((root / "route_context.json").read_text())
    course = _validate_course(root, context)
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()
              if line.strip()]
    if len(frames) < 3 or any(row["video_frame"] != index for index, row in enumerate(frames)):
        raise ValueError("Incomplete original video frame map")
    streams = {}
    for camera in CAMERAS:
        path = root / (camera + ".mkv")
        if not path.is_file():
            raise ValueError("Missing original camera source: " + camera)
        metadata = _probe(path)
        if (metadata.get("codec_name") != "ffv1" or
                metadata.get("r_frame_rate") != str(RATE_HZ) + "/1" or
                int(metadata.get("nb_read_frames", -1)) != len(frames) or
                int(metadata.get("width", 0)) <= 0 or int(metadata.get("height", 0)) <= 0):
            raise ValueError("Original camera source profile/frame count differs: " + camera)
        streams[camera] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "codec": "ffv1", "width": metadata["width"],
                           "height": metadata["height"], "frames": len(frames)}
    result["route_turn_direction_judgment"] = "original heading/road trace confirms right turn"
    return {"format": "c412593-saved-original-sources-v1", "measurement": result,
            "original_course": course,
            "original_cameras": streams, "frames": len(frames),
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}
