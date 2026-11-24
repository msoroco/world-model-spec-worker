"""Seal one original Native intersection attempt after owned resources close."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def _write_rows(path, rows):
    if path.exists():
        raise ValueError("Original Native output already exists: " + path.name)
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def _write(path, value):
    if path.exists():
        raise ValueError("Original Native output already exists: " + path.name)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def publish(output_dir, *, case_id, restoration, ffmpeg="ffmpeg"):
    root = Path(output_dir).resolve()
    original = root / "original-attempt"
    attempt = json.loads((original / "attempt.json").read_text())
    if attempt["case_id"] != case_id or attempt["acquisition_kind"] != "original_native":
        raise ValueError("Original Native attempt identity differs")
    if restoration.get("restored") is not True:
        raise ValueError("Cannot seal capture without verified Native restoration")
    pose = _rows(original / "pose.jsonl")
    frame_map = _rows(original / "frame-map.jsonl")
    if (len(pose) != 900 or len(frame_map) != 900 or
            any(row["frame"] != i or mapping["frame"] != i or
                row["world_frame"] != mapping["world_frame"] or
                abs(row["time_s"] - mapping["time_s"]) > 1e-9
                for i, (row, mapping) in enumerate(zip(pose, frame_map)))):
        raise ValueError("Original 900-frame pose and camera map join differs")
    for name in VIEWS:
        camera_dir = original / "cameras" / name
        if not camera_dir.is_dir() or any(
                not (camera_dir / f"{i:06d}.png").is_file()
                for i in range(900)):
            raise ValueError("Original Native camera frame missing: " + name)
    trace = [{"frame": row["world_frame"], "time_s": row["time_s"],
              "position": {"x": row["x_m"], "y": row["y_m"], "z": 0.0},
              "position_m": [row["x_m"], row["y_m"], 0.0],
              "heading_deg": row["heading_deg"], "speed_mps": row["speed_mps"],
              "original_pose_source": "original-attempt/pose.jsonl"}
             for row in pose]
    video_map = [{"video_frame": i, "carla_frame": row["world_frame"],
                  "time_s": row["time_s"]}
                 for i, row in enumerate(pose)]
    _write_rows(root / "trace.jsonl", trace)
    _write_rows(root / "video_frames.jsonl", video_map)
    encoders = {}
    for name in VIEWS:
        source = original / "cameras" / name / "%06d.png"
        target = root / (name + ".mkv")
        if target.exists():
            raise ValueError("Original Native video output already exists: " + name)
        command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-framerate", "20", "-i", str(source), "-frames:v", "900",
                   "-c:v", "ffv1", str(target)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        encoders[name] = result.returncode
        if result.returncode or not target.is_file():
            raise ValueError("Original Native video encoder failed: " + name + " " + result.stderr[-500:])
    packet_bytes = (original / "map-source.json").read_bytes()
    _write(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": case_id,
        "reviewed_map_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "original_attempt_sha256": hashlib.sha256((original / "attempt.json").read_bytes()).hexdigest(),
        "legal_necessity": "unresolved",
        "physical_acceptance_claimed": False})
    from worker_exchange.native_output import seal_capture
    seal = seal_capture(root, frames=900, restoration=restoration,
                        errors=[], encoder_exit_codes=encoders,
                        context={"case_id": case_id,
                                 "reviewed_map_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
                                 "original_pose_source": "original-attempt/pose.jsonl",
                                 "original_context_source": "original-attempt/context.jsonl"})
    return {"case_id": case_id, "frame_count": 900,
            "capture_seal_source_digest": seal["source_digest"],
            "physical_acceptance_claimed": False}
