"""Build a Native result only from timestamp joined saved observations.

This module reports measured source values. Runtime physical assessment remains
an independent engineering check; no legal right of way is decided here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(rows) != 900:
        raise ValueError(path.name + " must contain 900 original frames")
    return rows


def _recording_evidence(attempt: Path, packet: dict, camera_rows: list[dict],
                        description: dict) -> list[dict]:
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("derived recording channel directory already exists")
    channels.mkdir()
    raw = packet.get("raw_frames")
    observed = packet["frames"]
    if not isinstance(raw, list) or len(raw) != 900:
        raise ValueError("900 original raw Native observations required")
    device = json.loads((attempt / "signal-state-original.json").read_text()) if (
        attempt / "signal-state-original.json").is_file() else None
    signals = device.get("observed_signal_states", []) if device else []
    if signals and len(signals) != 900:
        raise ValueError("original signal readback does not span all frames")
    series = {
        "original_ego_body_speed": [
            {"body_xy_m": row["ego_body_xy_m"], "velocity_xy_mps": row["ego_velocity_xy_mps"],
             "front_station_m": obs["ego_front_station_m"], "speed_mps": obs["ego_speed_mps"]}
            for row, obs in zip(raw, observed)],
        "original_through_body": [
            {"body_xy_m": row["through_body_xy_m"],
             "center_xy_m": row["through_center_xy_m"],
             "center_station_m": obs["through_center_station_m"]}
            for row, obs in zip(raw, observed)],
        "original_view_rays": [row["native_view_raycast"] for row in raw],
        "original_device_control": [
            {"yield_sign": row["yield_sign_readback"],
             "signal_controlling": row["signal_controlling"],
             "officer_controlling": row["officer_controlling"],
             "signal_state": signals[i]["state"] if signals else None}
            for i, row in enumerate(raw)],
        "camera_frame_map": camera_rows,
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        body = "".join(json.dumps({"frame": obs["frame"], "time_s": obs["time_s"],
                                   "value": value}, separators=(",", ":")) + "\n"
                       for obs, value in zip(observed, series[name]))
        path.write_text(body)
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    context = packet["context"]
    authored = {
        "site_geometry": {"source_hashes": packet["site_source_hashes"],
                          "surveyed_context": context},
        "reference_exclusions": {key: context[key] for key in (
            "marked_stop_line", "near_side_crosswalk", "sidewalk_derived_crosswalk")},
        "governing_device": {key: context[key] for key in (
            "proper_yield_sign", "signal_controlling", "officer_controlling")},
    }
    for item in description["context_inputs"]:
        name = item["name"]
        path = channels / (name + ".json")
        path.write_text(json.dumps({name: authored[name]}, separators=(",", ":")) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": "channels/" + path.name})
    return evidence


def finalize(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    if config.get("selected_case_id") != report["case_id"]:
        raise ValueError("saved result belongs to another exact case")
    packet = json.loads((attempt / "nearest-view-original.json").read_text())
    frames = packet["frames"]
    trace = _rows(attempt / "trace.jsonl")
    mapping = _rows(attempt / "video_frames.jsonl")
    history = _rows(attempt / "interaction_history.jsonl")
    for i, (observed, tr, video, interaction) in enumerate(zip(frames, trace, mapping, history)):
        frame, time = observed["frame"], observed["time_s"]
        if (tr.get("frame") != frame or video.get("carla_frame") != frame or
                video.get("native_frame") != frame or video.get("video_frame") != i or
                interaction.get("frame") != frame or
                abs(tr.get("time_s", -1) - time) > 0.001 or
                abs(video.get("time_s", -1) - time) > 0.001 or
                abs(interaction.get("time_s", -1) - time) > 0.001):
            raise ValueError("original trace, interaction, and video frame join differs")
    if not (attempt / "control_context.json").is_file():
        raise ValueError("Missing required source: control_context.json")
    context = json.loads((attempt / "control_context.json").read_text())
    diagnostic_path = attempt / "fixture-provenance.json"
    diagnostic = (diagnostic_path.is_file() and
                  json.loads(diagnostic_path.read_text()).get("diagnostic_fixture") is True)
    required_kind = ("diagnostic_fixture_control_context" if diagnostic else
                     "original_native_control_context")
    if context.get("source_kind") != required_kind:
        raise ValueError("control context provenance differs")
    for name in VIEWS:
        if not (attempt / (name + ".mkv")).is_file():
            raise ValueError("Missing required source: " + name + ".mkv")
    if not (attempt / "raw.mkv").is_file():
        raise ValueError("Missing required source: raw.mkv")
    camera_rows = json.loads((attempt / "camera-frame-map.json").read_text())
    if len(camera_rows) != 900:
        raise ValueError("original four-camera frame map incomplete")
    sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
               for name in ("nearest-view-original.json", "camera-frame-map.json",
                            "camera-sources.json", "trace.jsonl", "video_frames.jsonl",
                            "interaction_history.jsonl", "control_context.json")}
    values = {name: item["value"] for name, item in report["measurements"].items()}
    target_checks = [{"target": name, "requested": "source_bound_observation",
                      "measured": value, "method": "saved_original_tick_measurement",
                      "tolerance": 0, "matched": False,
                      "physical_cause_confirmed": False,
                      "cause_evidence": "Source observation only; physical causation remains independent"}
                     for name, value in values.items()]
    result = {"case_id": report["case_id"], "measured_values": values,
              "target_checks": target_checks, "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original observations measured",
              "physical_failure_flags": {"detection_validated": False},
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS] + ["raw.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": _recording_evidence(
                  attempt, packet, camera_rows, config["case"]["recording_description"]),
              "realized_observables": {}, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(attempt, result)
    return validate_result(result)
