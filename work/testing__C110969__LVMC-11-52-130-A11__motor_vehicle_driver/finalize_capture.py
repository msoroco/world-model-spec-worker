"""Seal one original Native intersection attempt after owned resources close."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
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


def publish(output_dir, *, case_id, restoration, ffmpeg="ffmpeg", require_pipeline=False):
    root = Path(output_dir).resolve()
    original = root / "original-attempt"
    attempt = json.loads((original / "attempt.json").read_text())
    if attempt["case_id"] != case_id or attempt["acquisition_kind"] != "original_native":
        raise ValueError("Original Native attempt identity differs")
    if restoration.get("restored") is not True:
        raise ValueError("Cannot seal capture without verified Native restoration")
    pose = _rows(original / "pose.jsonl")
    road_source = attempt.get("road_source")
    if not isinstance(road_source, dict) or road_source.get("path") != "road.xodr":
        raise ValueError("Original loaded OpenDRIVE source binding missing")
    original_road = original / "road.xodr"
    if (not original_road.is_file() or
            hashlib.sha256(original_road.read_bytes()).hexdigest() != road_source.get("sha256")):
        raise ValueError("Original loaded OpenDRIVE source hash differs")
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
              "speed_mph": row["speed_mps"] / 0.44704,
              "original_pose_source": "original-attempt/pose.jsonl"}
             for row in pose]
    video_map = [{"video_frame": i, "carla_frame": row["world_frame"],
                  "time_s": row["time_s"]}
                 for i, row in enumerate(pose)]
    if require_pipeline:
        capture = root / "capture"
        if not (capture / "manifest.json").is_file():
            raise ValueError("Same-tick Native PipelineCapture is missing")
        manifest = json.loads((capture / "manifest.json").read_text())
        native_trace = _rows(root / "trace.jsonl")
        events = _rows(capture / "evidence.jsonl")
        frames = _rows(capture / "native/frames.jsonl")
        if (manifest.get("acquisition") != "original_live_run" or
                manifest.get("case_id") != case_id or
                manifest.get("extraction_confirmed") is not True or
                manifest.get("frames") != 900 or
                len(native_trace) != 900 or len(events) != 900 or len(frames) != 900):
            raise ValueError("Same-tick Native PipelineCapture is incomplete")
        for i, (pose_row, trace_row, event, frame_row) in enumerate(zip(pose, native_trace, events, frames)):
            source_frame = pose_row["world_frame"]
            if (trace_row["frame"] != source_frame or event["original_frame"] != source_frame or
                    event["replay_frame"] != source_frame or frame_row["frame"] != source_frame or
                    abs(trace_row["time_s"] - pose_row["time_s"]) > 1e-9 or
                    abs(event["recording_time_s"] - pose_row["time_s"]) > 1e-9 or
                    abs(trace_row["speed_mps"] - pose_row["speed_mps"]) > 1e-6):
                raise ValueError("Original Native graph/trace/pose frame join differs at " + str(i))
        if (hashlib.sha256((root / "road.xodr").read_bytes()).hexdigest() != road_source["sha256"] or
                manifest.get("sources", {}).get("road.xodr") != road_source["sha256"]):
            raise ValueError("Published loaded OpenDRIVE differs from original")
    else:
        _write_rows(root / "trace.jsonl", trace)
        if (root / "road.xodr").exists():
            raise ValueError("Original loaded OpenDRIVE output already exists")
        shutil.copyfile(original_road, root / "road.xodr")
        if hashlib.sha256((root / "road.xodr").read_bytes()).hexdigest() != road_source["sha256"]:
            raise ValueError("Published loaded OpenDRIVE differs from original")
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
