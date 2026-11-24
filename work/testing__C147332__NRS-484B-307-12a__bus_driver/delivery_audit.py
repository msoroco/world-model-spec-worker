"""Independent original-source, media and green-arrow behavior audit.

The diagnostic mode tests software on synthetic sources and never authorizes a
Native delivery. The default path requires a sealed original Native attempt.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from analysis import build_report


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ORIGINALS = ("road.xodr", "trace.jsonl", "video_frames.jsonl", "carla_recorder.log",
             "bus-body-history.jsonl", "lane-signal-history.jsonl",
             "sign-state-original.jsonl", "camera-frame-map.jsonl",
             "controller-history.jsonl", "reviewed-context.json", *[name + ".mkv" for name in CAMERAS])


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _recorded_sha(acquisition, name):
    item = acquisition.get(name)
    return item.get("sha256") if isinstance(item, dict) else item


def _decode(path, width, height):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames,width,height,avg_frame_rate,codec_name",
                            "-of", "json",
                            str(path)], capture_output=True, text=True, timeout=90)
    if probe.returncode:
        raise ValueError("original video frame probe failed: " + path.name)
    try:
        streams = json.loads(probe.stdout)["streams"]
        stream, = streams
        count = int(stream["nb_read_frames"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("original video frame probe failed: " + path.name) from exc
    if (count < 1 or stream.get("codec_name") != "ffv1" or
            stream.get("width") != width or stream.get("height") != height or
            stream.get("avg_frame_rate") != "20/1"):
        raise ValueError("original video capture profile mismatch: " + path.name)
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                            capture_output=True, text=True, timeout=120)
    if decode.returncode or decode.stderr.strip():
        raise ValueError("original video full decode failed: " + path.name)
    return count


def audit_attempt(path, *, diagnostic=False):
    path = Path(path)
    seal = _read(path / "capture-seal.json")
    acquisition = _read(path / "acquisition.json")
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True or
            any(seal.get("encoder_exit_codes", {}).get(name) != 0 for name in CAMERAS)):
        raise ValueError("original capture closure or encoder result incomplete")
    if not diagnostic and (seal.get("provenance_kind") != "native" or seal.get("diagnostic_fixture") is not False):
        raise ValueError("original Native acquisition required")
    if not diagnostic:
        exit_receipt = _read(path / "native-exit.json")
        if (exit_receipt.get("event") != "native_exit" or
                exit_receipt.get("capture_seal_sha256") != _sha(path / "capture-seal.json") or
                exit_receipt.get("native_process_exit_code") != 0 or
                exit_receipt.get("capture_command_failed") is not False):
            raise ValueError("successful original Native process exit unverified")
    for name, item in acquisition.items():
        rel = Path(name)
        if (rel.is_absolute() or ".." in rel.parts or not (path / rel).is_file() or
                _recorded_sha(acquisition, name) != _sha(path / rel)):
            raise ValueError("acquisition original source missing or changed: " + name)
        if seal.get("sources", {}).get(name) != _recorded_sha(acquisition, name):
            raise ValueError("acquisition source absent from closed capture: " + name)
    for name in ORIGINALS:
        original = path / name
        if (not original.is_file() or _recorded_sha(acquisition, name) != _sha(original) or
                seal.get("sources", {}).get(name) != _sha(original)):
            raise ValueError("original source missing or changed: " + name)
    frames = [json.loads(line) for line in (path / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    if not frames or len(frames) != seal.get("frames"):
        raise ValueError("sealed original frame count differs")
    numbers = [row.get("carla_frame") for row in frames]
    if any(type(number) is not int for number in numbers) or numbers != sorted(set(numbers)):
        raise ValueError("original frame identities invalid")
    camera_rows = [json.loads(line) for line in (path / "camera-frame-map.jsonl").read_text().splitlines() if line.strip()]
    if (len(camera_rows) != len(frames) or
            any(row.get("frame") != frame["carla_frame"] or
                row.get("elapsed_seconds") != frame.get("time_s") or
                row.get("camera_names") != list(CAMERAS)
                for row, frame in zip(camera_rows, frames))):
        raise ValueError("original camera/frame time join incomplete")
    decoded = {name: _decode(path / (name + ".mkv"),
                             1920 if name == "overview" else 1280,
                             1080 if name == "overview" else 720)
               for name in CAMERAS}
    if any(count != len(frames) for count in decoded.values()):
        raise ValueError("decoded original video frame count differs")
    report = build_report(path)
    suffix = _read(path / "scene.json").get("case_id", "").rsplit("__", 1)[-1]
    measured = report["measurements"]["green_arrow_bus_lane"]
    permission = measured["permission_observed_frames"]
    motion = measured["bus_moving_frames"]
    if suffix == "adjacent_dark_drive" and permission:
        raise ValueError("adjacent dark-lane baseline has measured green permission")
    if suffix in ("green_selected_drive", "second_green_drive", "green_selected_stand") and not permission:
        raise ValueError("expected full-body green-arrow coverage absent")
    if suffix == "green_selected_stand":
        if motion:
            raise ValueError("stationary green-arrow baseline moved")
        controls = [json.loads(line) for line in (path / "controller-history.jsonl").read_text().splitlines()
                    if line.strip()]
        if len(controls) != len(frames) or any(
                row.get("requested_control", {}).get("brake") != 1.0 or
                row.get("requested_control", {}).get("throttle") != 0.0
                for row in controls):
            raise ValueError("stationary bus hold request missing")
    elif suffix in ("green_selected_drive", "adjacent_dark_drive", "second_green_drive"):
        if not motion:
            raise ValueError("requested green-arrow probe travel absent")
    else:
        raise ValueError("unknown exact green-arrow case in original scene")
    return {"source_hashes": {name: _sha(path / name) for name in ORIGINALS},
            "decoded_frames": decoded, "site_review": report["site_review"],
            "measurements": report["measurements"],
            "diagnostic_fixture": diagnostic,
            "actual_pixels_reviewed": False, "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}
