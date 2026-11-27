"""Project verified original rail readbacks into the runtime recording shape.

This module accepts only a packet already admitted by ``verify_saved``. It
does not turn diagnostic pixels into physical evidence or make a legal ruling.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from rail_native_capture import CAMERAS
from rail_saved_measurement import _source


def _write_new(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError("rail derived output already exists: " + path.name)
    with path.open("x") as stream:
        stream.write(value)


def _jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                   for row in rows)


def project(attempt, packet, case_id, observation):
    """Use sealed Native frames and four decoded source videos after analysis."""
    attempt = Path(attempt).resolve()
    receipt = json.loads((attempt / "native-rail-receipt.json").read_text())
    frames = json.loads(_source(attempt, receipt["frames"]).read_text())
    camera_map = json.loads(_source(attempt, receipt["camera_map"]).read_text())
    if len(frames) != 900 or len(camera_map) != 900:
        raise ValueError("complete original railway frame history required")
    construction = json.loads((attempt / "construction.json").read_text())
    description = construction["recording_description"]
    videos = [name + ".mkv" for name in CAMERAS]
    hashes = {}
    for name in videos:
        path = attempt / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    trace, mapping, channel_rows = [], [], {item["name"]: [] for item in description["channels"]}
    positions = [row["position_xy_m"] for row in frames]
    derived_headings = []
    last_heading = None
    for index, position in enumerate(positions):
        following = next((candidate for candidate in positions[index + 1:]
                          if candidate != position), None)
        if following is not None:
            last_heading = math.degrees(math.atan2(
                following[1] - position[1], following[0] - position[0]))
        derived_headings.append(last_heading)
    if all(value is None for value in derived_headings):
        raise ValueError("original rail positions cannot establish trace heading")
    first_known = next(value for value in derived_headings if value is not None)
    derived_headings = [first_known if value is None else value for value in derived_headings]
    for index, (frame, cameras) in enumerate(zip(frames, camera_map)):
        identity = frame["original_frame"]
        time_s = frame["time_s"]
        if cameras.get("original_frame") != identity:
            raise ValueError("original rail frame/camera identity differs")
        position = frame["position_xy_m"]
        trace.append({"frame": identity, "time_s": time_s,
                      "position": {"x": position[0], "y": position[1], "z": 0.0},
                      "position_m": [position[0], position[1], 0.0],
                      "heading_deg": derived_headings[index],
                      "speed_mps": frame["speed_mps"],
                      "speed_mph": frame["speed_mps"] / 0.44704})
        mapping.append({"video_frame": index, "carla_frame": identity,
                        "native_frame": identity, "time_s": time_s})
        values = {
            "original_native_frame_history": {key: frame[key] for key in
                                              ("original_frame", "time_s", "route_station_m",
                                               "speed_mps", "body_on_crossing", "flagman_on_duty",
                                               "signal_installed", "signal_clearly_visible",
                                               "signal_immediate_train_approach")},
            "four_original_camera_streams": {
                "video_frame": index, "original_frame": identity,
                "source_sha256": {name: cameras["sources"][name]["sha256"]
                                  for name in CAMERAS}, "video_sha256": hashes},
        }
        for name in channel_rows:
            channel_rows[name].append({"time_s": time_s, "value": values[name]})
    if (attempt / "video_frames.jsonl").exists():
        observed = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
        if len(observed) != len(mapping) or any(
                any(row.get(key) != expected[key] for key in expected)
                for row, expected in zip(observed, mapping)):
            raise ValueError("composed rail video frame map differs from Native source")
    else:
        _write_new(attempt / "video_frames.jsonl", _jsonl(mapping))
    _write_new(attempt / "trace.jsonl", _jsonl(trace))
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        target = channels / (name + ".jsonl")
        _write_new(target, _jsonl(channel_rows[name]))
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(target.relative_to(attempt))})
    contexts = {"reviewed_map_source_sha256": packet["original_map_source"]["sha256"],
                "reviewed_packet_sha256": receipt["packet"]["sha256"]}
    context_path = channels / "reviewed_source_context.json"
    _write_new(context_path, json.dumps(contexts, sort_keys=True, indent=2) + "\n")
    evidence.extend({"name": item["name"], "unit": item["unit"],
                     "reference": str(context_path.relative_to(attempt))}
                    for item in description["context_inputs"])
    measured = observation.get("traversal_speed_mph_max")
    requested = json.loads((attempt / "config.json").read_text())["case"]["engineering_target_traversal_mph"]
    diagnostic = receipt.get("capture_kind") == "diagnostic_fixture"
    result = {
        "case_id": case_id, "measured_values": observation,
        "target_checks": [{"target": "railway traversal speed and sight setup",
                           "requested": requested, "measured": measured,
                           "method": "sealed original Native frame and three-ray readbacks",
                           "tolerance": 0.5,
                           "matched": abs(measured - requested) <= 0.5,
                           "physical_cause_confirmed": False,
                           "cause_evidence": contexts}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "saved rail measurement; physical and legal acceptance pending",
        "physical_failure_flags": {"independent_physical_review_pending": True},
        "trace_reference": "trace.jsonl", "video_references": videos,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {},
        "provenance_kind": "synthetic_fixture" if diagnostic else "original_native",
        "diagnostic_fixture": diagnostic,
    }
    _write_new(attempt / "result.json", json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result
