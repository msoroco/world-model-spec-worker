"""Publish factual Native channels and a nonlegal result from saved sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis import build as analyze

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = ("original_actor_state", "original_four_view_frame_map",
            "original_beam_pixels", "original_oncoming_distance")


def _source(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(root: Path, name: str) -> list[dict]:
    return [json.loads(x) for x in _source(root, name).read_text().splitlines() if x]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _channel(root: Path, name: str, values: list, times: list[float], unit: str) -> dict:
    target = root / (name + ".jsonl")
    if target.exists():
        raise ValueError("selected channel already exists: " + target.name)
    target.write_text("".join(json.dumps({"time_s": time, "value": value}, sort_keys=True) + "\n"
                              for time, value in zip(times, values)))
    return {"name": name, "unit": unit, "reference": target.name,
            "sha256": _hash(target)}


def publish(attempt: Path, *, expected_frames: int = 900,
            diagnostic: bool = False) -> dict:
    root = Path(attempt)
    report = analyze(root, expected_frames=expected_frames, diagnostic=diagnostic)
    config = json.loads(_source(root, "config.json").read_text())
    construction = json.loads(_source(root, "construction.json").read_text())
    if construction.get("case_id") != report["case_id"]:
        raise ValueError("selected construction does not bind original case")
    description = construction.get("recording_description")
    if not isinstance(description, dict) or {x.get("name") for x in description.get("channels", [])} != set(CHANNELS):
        raise ValueError("selected original recording channels differ")
    states = _rows(root, "actor-state.jsonl")
    cameras = _rows(root, "camera-frame-map.jsonl")
    rois = _rows(root, "roi-frames.jsonl")
    trace = _rows(root, "trace.jsonl")
    video = _rows(root, "video_frames.jsonl")
    if any(len(rows) != expected_frames for rows in (states, cameras, rois, trace, video)):
        raise ValueError("original Native source frame count differs")
    for index, (state, camera, roi, motion, frame) in enumerate(zip(states, cameras, rois, trace, video)):
        original = state.get("frame")
        if (camera.get("frame") != original or roi.get("frame") != original or
                motion.get("frame") != original or frame.get("carla_frame") != original or
                frame.get("video_frame") != index or
                any(abs(float(item.get("time_s", -1)) - float(state["time_s"])) > 1e-4
                    for item in (motion, frame))):
            raise ValueError("original Native/video source frame and time join differs")
    receipt = json.loads(_source(root, "native-source-receipt.json").read_text())
    if set(receipt.get("camera_movies", {})) != set(VIEWS):
        raise ValueError("four original Native camera movies required")
    for view in VIEWS:
        movie = _source(root, view + ".mkv")
        if receipt["camera_movies"][view]["sha256"] != _hash(movie):
            raise ValueError("original Native movie hash differs: " + view)
    times = [float(state["time_s"]) for state in states]
    evidence = [
        _channel(root, "original_actor_state", states, times, "structured record"),
        _channel(root, "original_four_view_frame_map", cameras, times, "structured record"),
        _channel(root, "original_beam_pixels", rois, times, "structured record"),
        _channel(root, "original_oncoming_distance", [
            {"frame": row["original_frame"],
             "body_gap_m": row["oncoming_body_gap_m"],
             "eye_gap_m": row["oncoming_eye_gap_m"]}
            for row in analyze_motion_rows(root, receipt, expected_frames, config["case_plan"])],
                 times, "m"),
    ]
    context_path = root / "reviewed_highway_time_lamp_and_contour.json"
    if context_path.exists():
        raise ValueError("selected reviewed site context already exists")
    context_path.write_text(json.dumps({"reviewed_site": json.loads(
        _source(root, "site-packet.json").read_text())}, sort_keys=True) + "\n")
    evidence.append({"name": "reviewed_highway_time_lamp_and_contour",
                     "unit": "structured record", "reference": context_path.name,
                     "sha256": _hash(context_path)})
    values = report["measurements"]
    measured = {"frame_count": expected_frames,
                "within_500ft_frame_count": values["beam_requirement_2"]["value"]["within_500ft_frame_count"],
                "original_lamp_readback_count": len(values["beam_requirement_3"]["value"]["lamp_readback_bits_by_frame"])}
    target = {"target": "requested_beam_and_oncoming_geometry",
              "requested": {"beam": config["case_plan"]["requested_beam"],
                            "start_separation_ft": config["case_plan"]["requested_start_body_gap_ft"]},
              "measured": measured,
              "method": "original 20 Hz actor geometry, lamp readback and camera pixels",
              "tolerance": "complete original 900-frame interval; no legal glare or safe-distance tolerance",
              "matched": False, "physical_cause_confirmed": False,
              "cause_evidence": "Actual physical beam and eye ray projection require original calibrated review"}
    return {"case_id": report["case_id"], "measured_values": measured,
            "target_checks": [target], "setup_confirmed": False,
            "behavior_attempted": True, "maneuver_completed": False,
            "termination_reason": "original planned frames exhausted; saved physical review pending",
            "physical_failure_flags": {"actual_beam_and_glare_unverified": True},
            "trace_reference": "trace.jsonl",
            "video_references": [view + ".mkv" for view in VIEWS],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": description,
            "recording_evidence": evidence,
            "realized_observables": {}, "physical_acceptance_claimed": False,
            "diagnostic_fixture": diagnostic}


def analyze_motion_rows(root: Path, receipt: dict, expected_frames: int, case: dict) -> list[dict]:
    from beam_measure import measure
    return measure(root, receipt["source_hashes"], expected_frames=expected_frames,
                   case=case)["rows"]
