"""Independent original-source, media and red-X behavior audit.

The diagnostic mode tests software on synthetic sources and never authorizes a
Native delivery. The default path requires a sealed original Native attempt.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from analysis import build_report
from stationary_hold import audit as audit_stationary_hold


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


def _decode(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1",
                            str(path)], capture_output=True, text=True, timeout=90)
    if probe.returncode or not probe.stdout.strip().isdigit():
        raise ValueError("original video frame probe failed: " + path.name)
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                            capture_output=True, text=True, timeout=120)
    if decode.returncode or decode.stderr.strip():
        raise ValueError("original video full decode failed: " + path.name)
    return int(probe.stdout.strip())


def _verify_original_pixels(path, expected_hashes, *, width, height):
    """Compare every lossless video frame with the BGRA bytes received by Native."""
    size = width * height * 4
    process = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path),
                                "-f", "rawvideo", "-pix_fmt", "bgra", "pipe:1"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for index, expected in enumerate(expected_hashes):
            raw = process.stdout.read(size)
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("original camera pixel bytes differ: " + path.name +
                                 " frame " + str(index))
        if process.stdout.read(1):
            raise ValueError("original camera has extra decoded pixel frames: " + path.name)
        stderr = process.stderr.read()
        if process.wait(timeout=120) != 0 or stderr:
            raise ValueError("original camera pixel decode failed: " + path.name)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


def _verify_pixel_map(path, rows):
    expected = {name: [] for name in CAMERAS}
    for row in rows:
        hashes = row.get("original_bgra_sha256")
        if not isinstance(hashes, dict) or set(hashes) != set(CAMERAS):
            raise ValueError("original camera pixel hash map missing")
        for name in CAMERAS:
            value = hashes[name]
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("original camera pixel hash invalid: " + name)
            expected[name].append(value)
    for name in CAMERAS:
        width, height = (1920, 1080) if name == "overview" else (1280, 720)
        _verify_original_pixels(path / (name + ".mkv"), expected[name], width=width, height=height)


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
    decoded = {name: _decode(path / (name + ".mkv")) for name in CAMERAS}
    if any(count != len(frames) for count in decoded.values()):
        raise ValueError("decoded original video frame count differs")
    if not diagnostic:
        _verify_pixel_map(path, camera_rows)
    report = build_report(path)
    suffix = _read(path / "scene.json").get("case_id", "").rsplit("__", 1)[-1]
    measured = report["measurements"]["red_x_bus_lane"]
    if suffix == "adjacent_travel" and (measured["red_x_entry_frames"] or measured["red_x_driving_frames"]):
        raise ValueError("adjacent-lane baseline entered or drove in red-X lane")
    if suffix == "lateral_entry" and not measured["red_x_entry_frames"]:
        raise ValueError("lateral red-X lane entry absent")
    if suffix == "red_lane_stand":
        if measured["red_x_driving_frames"]:
            raise ValueError("stationary red-X lane baseline moved")
        audit_stationary_hold(path)
    if suffix == "red_lane_drive" and not measured["red_x_driving_frames"]:
        raise ValueError("red-X in-lane driving absent")
    if suffix not in ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive"):
        raise ValueError("unknown exact red-X case in original scene")
    return {"source_hashes": {name: _sha(path / name) for name in ORIGINALS},
            "decoded_frames": decoded, "site_review": report["site_review"],
            "measurements": report["measurements"],
            "diagnostic_fixture": diagnostic,
            "original_pixel_bytes_verified": not diagnostic,
            "actual_pixels_reviewed": False, "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}
