"""Independent sealed-source and saved-observation audit for C150041.

Diagnostic mode tests software only. Normal mode additionally requires Native
provenance and exit; neither mode claims that camera pixels prove legal facts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from parking_cameras import CAMERAS
from parking_finalizer import finalize
from parking_scene import ASSIGNMENT
from source_review import validate


ORIGINALS = ("road.xodr", "trace.jsonl", "video_frames.jsonl", "carla_recorder.log",
             "parking-history.jsonl", "camera-frame-map.jsonl", "controller-history.jsonl",
             "reviewed-context.json", "construction.json", "runner.py",
             *(name + ".mkv" for name in CAMERAS))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _decode(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1",
                            str(path)], capture_output=True, text=True, timeout=90)
    if probe.returncode or not probe.stdout.strip().isdigit():
        raise ValueError("original camera frame probe failed: " + path.name)
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                            capture_output=True, text=True, timeout=120)
    if decode.returncode or decode.stderr.strip():
        raise ValueError("original camera full decode failed: " + path.name)
    return int(probe.stdout.strip())


def verify_native_map_binding(root, packet, source_hashes):
    """Join retained OpenDRIVE and pipeline map identity to reviewed context."""
    root = Path(root)
    context = packet.get("context", {})
    expected_hash = context.get("native_opendrive_sha256")
    expected_name = context.get("native_map_name")
    if not expected_hash or not expected_name:
        raise ValueError("reviewed Native map identity missing")
    road = root / "road.xodr"
    if not road.is_file() or _sha(road) != expected_hash or source_hashes.get("road.xodr") != expected_hash:
        raise ValueError("original OpenDRIVE differs from reviewed Native map")
    manifest = root / "capture/manifest.json"
    if (not manifest.is_file() or source_hashes.get("capture/manifest.json") != _sha(manifest) or
            _read(manifest).get("map") != expected_name):
        raise ValueError("original pipeline map name differs from reviewed Native map")


def audit_attempt(attempt, *, diagnostic=False, decoder=None):
    root = Path(attempt)
    seal = _read(root / "capture-seal.json")
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True or
            any(seal.get("encoder_exit_codes", {}).get(name) != 0 for name in CAMERAS)):
        raise ValueError("original capture closure or encoder result incomplete")
    if not diagnostic:
        if seal.get("provenance_kind") != "native" or seal.get("diagnostic_fixture") is not False:
            raise ValueError("original Native acquisition required")
        exit_receipt = _read(root / "native-exit.json")
        if (exit_receipt.get("event") != "native_exit" or
                exit_receipt.get("capture_seal_sha256") != _sha(root / "capture-seal.json") or
                exit_receipt.get("native_process_exit_code") != 0 or
                exit_receipt.get("capture_command_failed") is not False):
            raise ValueError("successful original Native process exit unverified")
    source_hashes = seal.get("sources", {})
    for name in ORIGINALS:
        path = root / name
        if not path.is_file() or source_hashes.get(name) != _sha(path):
            raise ValueError("sealed original source missing or changed: " + name)
    context = validate(root / "reviewed-context.json", source_root=root)
    packet = _read(root / "reviewed-context.json")
    if not diagnostic:
        verify_native_map_binding(root, packet, source_hashes)
    for descriptor in packet["sources"].values():
        name = descriptor["path"]
        if source_hashes.get(name) != _sha(root / name):
            raise ValueError("reviewed source absent from sealed capture: " + name)
    scene = _read(root / "scene.json") if (root / "scene.json").is_file() else _read(root / "construction.json")
    case_id = scene.get("case_id", "")
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("sealed construction case identity differs")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if (scene.get("source_packet_sha256") != context["reviewed_packet_sha256"] or
            scene.get("activity_request") != context["activity"]):
        raise ValueError("sealed construction and reviewed activity differ")
    frames = _rows(root / "video_frames.jsonl")
    camera_rows = _rows(root / "camera-frame-map.jsonl")
    history = _rows(root / "parking-history.jsonl")
    trace = _rows(root / "trace.jsonl")
    controller = _rows(root / "controller-history.jsonl")
    if not frames or any(len(rows) != len(frames) for rows in
                         (camera_rows, history, trace, controller)) or len(frames) != seal.get("frames"):
        raise ValueError("sealed original frame count differs")
    previous = -1
    for video_index, (frame, camera, body, movement, request) in enumerate(
            zip(frames, camera_rows, history, trace, controller)):
        identity = frame.get("carla_frame")
        time_s = frame.get("time_s")
        if (frame.get("video_frame") != video_index or type(identity) is not int or
                identity <= previous or
                any(row.get("frame") != identity or row.get("time_s") != time_s
                    for row in (camera, body, movement, request)) or
                camera.get("camera_names") != list(CAMERAS)):
            raise ValueError("original body/trace/camera/control frame join incomplete")
        previous = identity
    decoder = decoder or _decode
    decoded = {name: decoder(root / (name + ".mkv")) for name in CAMERAS}
    if any(count != len(frames) for count in decoded.values()):
        raise ValueError("decoded original camera frame count differs")
    measured = finalize(root / "reviewed-context.json", root, suffix,
                        root / "parking-history.jsonl", source_hashes["parking-history.jsonl"])
    return {"case_id": case_id, "source_hashes": {name: source_hashes[name] for name in ORIGINALS},
            "decoded_frames": decoded, "saved_observations": measured,
            "diagnostic_fixture": diagnostic, "actual_pixels_reviewed": False,
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
