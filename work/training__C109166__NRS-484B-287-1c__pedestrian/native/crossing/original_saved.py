"""Saved-only original source join for the two controlled crossing locations.

This measures where the recorded pedestrian footprint entered the roadway and
whether both surveyed controls were operating. It never supplies a legal verdict.
"""

import hashlib
import json
import math
from pathlib import Path
import subprocess

from original_capture import CAMERAS, FRAMES, RATE, check_config, sha


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()]


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _inside(point, polygon):
    x, y = point
    inside = False
    last = polygon[-1]
    for current in polygon:
        if (current[1] > y) != (last[1] > y):
            crossing_x = (last[0] - current[0]) * (y - current[1]) / (last[1] - current[1]) + current[0]
            if x < crossing_x:
                inside = not inside
        last = current
    return inside


def _decode_video(path, width, height, expected_hashes):
    command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(path)]
    probe = subprocess.run(command, text=True, capture_output=True, timeout=180)
    if probe.returncode:
        raise ValueError("Original camera probe failed: " + path.name)
    streams = json.loads(probe.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("width") != width
            or streams[0].get("height") != height
            or int(streams[0].get("nb_read_frames", -1)) != FRAMES):
        raise ValueError("Original camera profile or frame count differs: " + path.name)
    decoder = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_bytes = width * height * 3
    try:
        for index, expected in enumerate(expected_hashes):
            chunks = []
            remaining = frame_bytes
            while remaining:
                part = decoder.stdout.read(remaining)
                if not part:
                    raise ValueError("Original camera pixel frame missing: " + path.name)
                chunks.append(part)
                remaining -= len(part)
            if hashlib.sha256(b"".join(chunks)).hexdigest() != expected:
                raise ValueError("Original camera decoded pixel hash differs at frame " + str(index))
        if decoder.stdout.read(1):
            raise ValueError("Original camera has extra decoded pixels: " + path.name)
        if decoder.wait(timeout=300) != 0:
            raise ValueError("Original camera full decode failed: " + path.name)
    finally:
        if decoder.poll() is None:
            decoder.kill()
            decoder.wait()
        decoder.stdout.close()
        decoder.stderr.close()


def measure(attempt, *, decode_video=True):
    attempt = Path(attempt)
    names = ("config.json", "acquisition-provenance.json", "native-survey.json", "native-survey-provenance.json",
             "native-capture-report.json", "video_frames.jsonl", "trace.jsonl",
             "pedestrian-original.jsonl", "controls-original.jsonl", "camera-sources.jsonl")
    source_hashes = {name: sha(required(attempt, name)) for name in names}
    config = json.loads(required(attempt, "config.json").read_text())
    check_config(config)
    acquisition = json.loads(required(attempt, "acquisition-provenance.json").read_text())
    survey = json.loads(required(attempt, "native-survey.json").read_text())
    provenance = json.loads(required(attempt, "native-survey-provenance.json").read_text())
    report = json.loads(required(attempt, "native-capture-report.json").read_text())
    if acquisition.get("provenance_kind") == "native":
        if (acquisition.get("diagnostic_fixture") is not False
                or survey.get("review_status") != "independently_reviewed"
                or not required(attempt, "capture-seal.json").is_file()):
            raise ValueError("Native crossing requires reviewed original survey and capture seal")
    elif acquisition.get("provenance_kind") == "synthetic_fixture":
        if acquisition.get("diagnostic_fixture") is not True or survey.get("review_status") != "synthetic_diagnostic":
            raise ValueError("Diagnostic crossing must identify synthetic fixture provenance")
    else:
        raise ValueError("Original acquisition provenance missing")
    if (provenance.get("copied_sha256") != source_hashes["native-survey.json"]
            or report.get("case_id") != config.get("case_id")
            or report.get("frames") != FRAMES
            or report.get("expected_frames") != FRAMES
            or report.get("error") is not None
            or report.get("survey_sha256") != source_hashes["native-survey.json"]
            or report.get("restoration", {}).get("restored") is not True):
        raise ValueError("Original capture or restoration evidence incomplete")
    media = provenance.get("copied_media")
    if not isinstance(media, dict) or len(media) != 4:
        raise ValueError("Four independent original survey media sources required")
    for name, digest in media.items():
        path = required(attempt, "native-survey-media/" + name)
        if sha(path) != digest:
            raise ValueError("Original survey media changed: " + name)
        source_hashes["native-survey-media/" + name] = digest
    mapping = rows(attempt, "video_frames.jsonl")
    trace = rows(attempt, "trace.jsonl")
    pedestrians = rows(attempt, "pedestrian-original.jsonl")
    controls = rows(attempt, "controls-original.jsonl")
    camera_rows = rows(attempt, "camera-sources.jsonl")
    if not all(len(group) == FRAMES for group in (mapping, trace, pedestrians, controls)):
        raise ValueError("Original 600-frame participant and trace sources required")
    if len(camera_rows) != FRAMES * len(CAMERAS):
        raise ValueError("Four original camera sources per frame required")
    control_ids = {item["native_actor_id"] for item in survey["controls"]}
    entry = None
    prior_frame = -1
    prior_time = -1.0
    prior_y = None
    for index, (frame, sample, pedestrian, device) in enumerate(
            zip(mapping, trace, pedestrians, controls)):
        native = frame.get("native_frame")
        time_s = frame.get("time_s")
        if (frame.get("video_frame") != index or type(native) is not int
                or native <= prior_frame or not _number(time_s) or time_s <= prior_time
                or frame.get("carla_frame") != native
                or any(row.get("native_frame", row.get("frame")) != native
                       for row in (sample, pedestrian, device))):
            raise ValueError("Original trace, participant and FrameMap join differs")
        if (not _number(pedestrian.get("time_s"))
                or abs(pedestrian["time_s"] - time_s) > 1e-4
                or not _number(device.get("time_s"))
                or abs(device["time_s"] - time_s) > 1e-4):
            raise ValueError("Original participant times differ")
        center = pedestrian.get("center_xy_m")
        footprint = pedestrian.get("footprint_xy_m")
        if (not isinstance(center, list) or len(center) != 2
                or not all(_number(v) for v in center)
                or not isinstance(footprint, list) or len(footprint) != 4
                or any(not isinstance(p, (list, tuple)) or len(p) != 2
                       or not all(_number(v) for v in p) for p in footprint)):
            raise ValueError("Original pedestrian footprint incomplete")
        if not isinstance(device.get("controls"), list) or len(device["controls"]) != 2:
            raise ValueError("Two original device observations required")
        if {item.get("native_actor_id") for item in device["controls"]} != control_ids:
            raise ValueError("Original device identities differ from survey")
        observed_entry = prior_y is not None and prior_y < survey["roadway_boundary"]["entry_y_m"] <= center[1]
        if pedestrian.get("roadway_entry_observed") is not observed_entry:
            raise ValueError("Recorded roadway entry differs from original footprint trajectory")
        if observed_entry:
            if entry is not None:
                raise ValueError("Multiple roadway entries observed")
            entry = {"video_frame": index, "native_frame": native, "time_s": time_s,
                     "center_xy_m": center, "footprint_xy_m": footprint,
                     "both_controls_operating": all(item.get("operating_observed") is True
                                                    and item.get("native_state") in ("Red", "Yellow", "Green")
                                                    for item in device["controls"]),
                     "within_marked_crosswalk_polygon": _inside(
                         center, survey["marked_crosswalk"]["polygon_xy_m"])}
        for camera_index, (name, width, height) in enumerate(CAMERAS):
            item = camera_rows[index * len(CAMERAS) + camera_index]
            if (item.get("camera") != name or item.get("video_frame") != index
                    or item.get("native_frame") != native
                    or not _number(item.get("time_s")) or abs(item["time_s"] - time_s) > 1e-4
                    or (item.get("width"), item.get("height")) != (width, height)
                    or item.get("rgb_sha256") != frame.get("source_rgb_sha256", {}).get(name)):
                raise ValueError("Original camera pixel/frame join differs")
        prior_frame, prior_time, prior_y = native, time_s, center[1]
    if entry is None:
        raise ValueError("Original pedestrian roadway entry not observed")
    if not entry["both_controls_operating"]:
        raise ValueError("Both official controls were not operating at roadway entry")
    expected_marked = config["requested_crossing_location"] == "marked_crosswalk"
    if entry["within_marked_crosswalk_polygon"] is not expected_marked:
        raise ValueError("Original crossing location differs from selected case")
    for name, width, height in CAMERAS:
        path = required(attempt, name + ".mkv")
        if decode_video:
            _decode_video(path, width, height, [camera_rows[index * len(CAMERAS) + camera_index]["rgb_sha256"]
                                                for index in range(FRAMES)
                                                for camera_index, camera in enumerate(CAMERAS)
                                                if camera[0] == name])
        source_hashes[name + ".mkv"] = sha(path)
    return {"case_id": config["case_id"], "entry": entry,
            "original_frames": FRAMES, "original_camera_count": len(CAMERAS),
            "source_sha256": source_hashes,
            "exception_484b_290_applicability": "undetermined_pending_independent_source_review",
            "legal_verdict": None, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.attempt), indent=2, allow_nan=False))
