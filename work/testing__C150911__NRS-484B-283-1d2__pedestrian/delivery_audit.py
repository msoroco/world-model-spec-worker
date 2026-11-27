"""Independent original-source and full-video delivery audit.

This checks saved evidence and rejects synthetic fixtures outside diagnostic mode.
It does not certify statutory compliance or camera visibility of the pedestrian.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot, isfinite
import subprocess
from pathlib import Path

ASSIGNMENT = "testing__C150911__NRS-484B-283-1d2__pedestrian"
SOURCE = "original-countdown-observations.json"
RECEIPT = "original-countdown-receipt.json"
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
    "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def point(value) -> tuple[float, float]:
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) not in (int, float) or not isfinite(x) for x in value)):
        raise ValueError("original pedestrian coordinate missing")
    return float(value[0]), float(value[1])


def in_polygon(value, polygon) -> bool:
    x, y = point(value)
    inside = False
    for i, item in enumerate(polygon):
        x1, y1 = point(item)
        x2, y2 = point(polygon[(i + 1) % len(polygon)])
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def audit(attempt: Path, case_id: str, diagnostic: bool = False) -> dict:
    attempt = attempt.resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    packet_path = required(attempt, SOURCE)
    packet = json.loads(packet_path.read_text())
    receipt = json.loads(required(attempt, RECEIPT).read_text())
    if (not case_id.startswith(ASSIGNMENT + "__") or
            config.get("selected_case_id") != case_id or
            packet.get("case_id") != case_id or
            packet.get("assignment_id") != ASSIGNMENT or
            receipt.get("case_id") != case_id or
            receipt.get("source_sha256") != sha(packet_path) or
            receipt.get("fps") != 20 or
            packet.get("diagnostic_fixture") is not diagnostic or
            receipt.get("diagnostic_fixture") is not diagnostic):
        raise ValueError("original countdown source receipt or identity differs")
    site = packet.get("site", {})
    if (site.get("cell_id") != "C150911" or
            site.get("layout") != "one_way_road" or
            site.get("highway_public_vehicular_access") is not True or
            site.get("signal_facing_pedestrian") is not True):
        raise ValueError("original one-way public highway or facing signal missing")
    frames = packet.get("frames")
    if not isinstance(frames, list) or (not diagnostic and len(frames) != 900):
        raise ValueError("original 900-frame countdown history missing")
    mapping = lines(required(attempt, "video_frames.jsonl"))
    trace = lines(required(attempt, "trace.jsonl"))
    if (len(frames) != receipt.get("frame_count") or
            len(mapping) != len(frames) or len(trace) != len(frames)):
        raise ValueError("original countdown frame stream lengths differ")
    if not diagnostic and packet.get("original_trace_id") != "Native:" + sha(attempt / "trace.jsonl"):
        raise ValueError("original countdown trace source differs")
    entry = completion = zero = None
    identity = None
    expected_form = ("wait" if case_id.endswith("_wait") else
        "upraised_hand" if case_id.endswith("_hand") else "dont_walk")
    expected_direction = "reverse" if case_id.endswith("_reverse") else "forward"
    target = site.get("crossing_routes", {}).get(expected_direction, {}).get("waypoints_xy", [])
    if len(target) < 3:
        raise ValueError("original crossing route missing")
    target = point(target[-1])
    polygon = site.get("highway_polygon_xy")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("original highway polygon missing")
    prior_value = None
    entered = False
    for i, (frame, mapped, native) in enumerate(zip(frames, mapping, trace)):
        number = frame.get("original_frame")
        if (type(number) is not int or
                (i and number != frames[i - 1]["original_frame"] + 1) or
                mapped.get("video_frame") != i or
                mapped.get("native_frame") != number or
                mapped.get("carla_frame") != number or native.get("frame") != number or
                any(abs(value.get("time_s", -1) - frame.get("time_s", -2)) > .0001
                    for value in (mapped, native))):
            raise ValueError("original countdown frame/time join differs")
        if (not frame.get("signal_readback_sha256") or
                not frame.get("pedestrian_pose_sha256") or
                frame.get("site_source_sha256") != site.get("signal_source_sha256") or
                type(frame.get("illuminated")) is not bool or
                type(frame.get("flashing")) is not bool or
                type(frame.get("countdown_present")) is not bool or
                frame.get("signal_facing_direction") not in (expected_direction, "both")):
            raise ValueError("original signal/countdown readback missing")
        value = frame.get("countdown_value")
        if frame["countdown_present"]:
            if type(value) is not int or value < 0:
                raise ValueError("legible original countdown value missing")
            if prior_value is not None and not prior_value - 1 <= value <= prior_value:
                raise ValueError("original countdown sequence invalid")
            prior_value = value
        elif not (zero is not None and not frame["flashing"] and value is None):
            raise ValueError("countdown disappeared before displayed zero")
        if frame["flashing"] and not (frame["illuminated"] and
                frame["countdown_present"] and frame.get("signal_form") == expected_form):
            raise ValueError("flashing indication form or countdown differs")
        if frame.get("pedestrian_id") is None:
            raise ValueError("original pedestrian identity missing")
        if identity is None:
            identity = frame["pedestrian_id"]
        if frame["pedestrian_id"] != identity:
            raise ValueError("original pedestrian identity changed")
        if value == 0 and zero is None:
            zero = number
        position = point(frame.get("pedestrian_xy"))
        inside = in_polygon(frame["pedestrian_xy"], polygon)
        if frame.get("in_highway") is not inside:
            raise ValueError("recorded highway membership differs from original pose")
        entered = entered or inside
        derived_complete = entered and not inside and hypot(
            position[0] - target[0], position[1] - target[1]) <= .5
        if frame.get("crossing_complete") is not derived_complete:
            raise ValueError("recorded crossing completion differs from original pose")
        if inside and entry is None:
            if not (frame["illuminated"] and frame["flashing"] and value is not None and value > 0):
                raise ValueError("entry did not occur during illuminated flashing countdown")
            entry = number
        if derived_complete and completion is None:
            completion = number
        if not isinstance(frame.get("exception_context"), dict):
            raise ValueError("original statutory exception context missing")
    if entry is None or completion is None or zero is None or not entry < completion:
        raise ValueError("original entry, completion or zero absent")
    relation = "before_zero" if completion < zero else "at_zero" if completion == zero else "after_zero"
    if not case_id.endswith("__" + relation + "_dont_walk") and not case_id.endswith("__before_zero_wait") and not case_id.endswith("__before_zero_hand") and not case_id.endswith("__before_zero_reverse"):
        raise ValueError("original completion relation differs from case")
    if case_id.endswith(("_wait", "_hand", "_reverse")) and relation != "before_zero":
        raise ValueError("original completion relation differs from case")
    media = {}
    for camera, dimensions in CAMERAS.items():
        path = required(attempt, camera + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries",
            "stream=nb_read_frames,codec_name,width,height,r_frame_rate",
            "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
        if probe.returncode:
            raise ValueError("four-camera ffprobe failed: " + camera)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or int(streams[0]["nb_read_frames"]) != len(frames):
            raise ValueError("four-camera frame count differs: " + camera)
        stream = streams[0]
        if not diagnostic and (stream.get("codec_name") != "ffv1" or
                (stream.get("width"), stream.get("height")) != dimensions or
                stream.get("r_frame_rate") != "20/1"):
            raise ValueError("original video codec, size or rate differs: " + camera)
        decoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-nostdin", "-i", str(path), "-f", "null", "-"],
            capture_output=True, timeout=120)
        if decoded.returncode:
            raise ValueError("four-camera full decode failed: " + camera)
        media[camera] = {"sha256": sha(path), "frames": len(frames)}
    return {"format": "worker-independent-countdown-delivery",
        "case_id": case_id, "passed": True, "diagnostic_only": diagnostic,
        "frame_count": len(frames), "source_sha256": sha(packet_path),
        "entry_original_frame": entry, "completion_original_frame": completion,
        "first_zero_original_frame": zero, "completion_relation": relation,
        "full_video_decode": media, "physical_acceptance": False,
        "legal_acceptance": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    value = audit(args.attempt, args.case_id, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case_id, "passed": True}))


if __name__ == "__main__":
    main()
