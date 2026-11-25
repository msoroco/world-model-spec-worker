"""Finalize exact subsection 2 cases from retained original sources only."""

import argparse
import hashlib
import json
from pathlib import Path

from intersection_yield_measure import CAMERAS, SOURCES, analyze


PREFIX = "testing__C158196__NRS-484B-257-2__motor_vehicle_driver__"
SUFFIXES = {
    "active_signal_controls", "signal_off_signed_duty",
    "signal_elsewhere_no_control", "signal_off_stop_signed_duty",
    "approaching_traffic_close", "approaching_traffic_far",
}
CHANNELS = {
    "signal_state": ("text", lambda s: s["signal_state"]),
    "operative_signal_control": ("count", lambda s: int(s["signal_controls_ego"] and s["signal_state"] != "Off")),
    "ego_crossing_body": ("structured record", lambda s: s["ego_body_vertices_xy_m"]),
    "other_crossing_body": ("structured record", lambda s: s["other_body_vertices_xy_m"]),
    "ego_approach_speed": ("m/s", lambda s: s["ego_speed_mps"]),
    "other_approach_speed": ("m/s", lambda s: s["other_speed_mps"]),
    "ego_time_to_conflict": ("structured record", lambda s: {"defined": s["ego_time_to_conflict_s"] is not None, "value_s": s["ego_time_to_conflict_s"]}),
    "other_time_to_conflict": ("structured record", lambda s: {"defined": s["other_time_to_conflict_s"] is not None, "value_s": s["other_time_to_conflict_s"]}),
}


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_saved(attempt):
    attempt = Path(attempt)
    required = ("config.json", "trace.jsonl", "capture/evidence.jsonl", *SOURCES,
                *(name + ".mkv" for name in CAMERAS))
    for name in required:
        path = attempt / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(PREFIX) or
            case_id[len(PREFIX):] not in SUFFIXES or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-257-2", "C158196", "motor_vehicle_driver")):
        raise ValueError("Wrong exact subsection 2 case identity")
    report = analyze(attempt)
    history = _rows(attempt / "crossing_history.jsonl")
    frames = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    evidence = _rows(attempt / "capture/evidence.jsonl")
    if not (len(history) == len(frames) == len(trace) == len(evidence)):
        raise ValueError("Original Native histories have different lengths")
    for crossing, frame, motion, event in zip(history, frames, trace, evidence):
        fid, time_s = frame["carla_frame"], frame["time_s"]
        if (crossing["frame"] != fid or crossing["time_s"] != time_s or
                motion.get("frame") != fid or event.get("original_frame") != fid):
            raise ValueError("Original trace or evidence frame join failed")
        if "time_s" in motion and abs(motion["time_s"] - time_s) > 1e-4:
            raise ValueError("Original trace timestamp join failed")
    return config, report, history, frames, {name: _sha(attempt / name) for name in required}


def measure_operative_signal_at_entry(report):
    return report["operative_signal_controls_ego_at_entry_observed"]


def measure_ego_entrance_device(report):
    return report["ego_entrance_device"]


def measure_other_inside_at_entry(report):
    return report["other_inside_at_ego_entry"]


def measure_stopped_before_entry(report):
    return report["stopped_before_entry_observed"]


def finalize(attempt, output):
    """Write observational channels, native result and a separate analysis."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Choose a fresh attempt; retained evidence cannot be overwritten")
    config, report, history, frames, hashes = validate_saved(attempt)
    channels = attempt / "channels"
    channels.mkdir()
    evidence = []
    for name, (unit, getter) in CHANNELS.items():
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for frame, source, sample in zip(frames, history, report["samples"]):
                value = getter(source if name.endswith("body") or name.endswith("speed") else sample)
                stream.write(json.dumps({"original_frame": frame["carla_frame"],
                                         "time_s": frame["time_s"], "value": value},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": unit, "reference": "channels/" + path.name})
    context_path = channels / "entrance_inventory.json"
    context_path.write_text(json.dumps({"entrance_inventory": json.loads((attempt / "entrance_inventory.json").read_text())}, allow_nan=False) + "\n")
    evidence.append({"name": "entrance_inventory", "unit": "structured record", "reference": "channels/entrance_inventory.json"})
    case_id = config["selected_case_id"]
    suffix = case_id[len(PREFIX):]
    entry_control = report["operative_signal_controls_ego_at_entry_observed"]
    expected_control = suffix == "active_signal_controls"
    expected_device = "stop" if suffix == "signal_off_stop_signed_duty" else "yield"
    checks = [
        {"target": "operative_signal_at_entry", "requested": expected_control,
         "measured": entry_control, "method": "original affected-lane and state join at first body entry",
         "tolerance": 0, "matched": entry_control is expected_control,
         "physical_cause_confirmed": False,
         "cause_evidence": ["entrance_inventory.json", "crossing_history.jsonl", "video_frames.jsonl"]},
        {"target": "ego_entrance_device", "requested": expected_device,
         "measured": report["ego_entrance_device"], "method": "saved entrance inventory",
         "tolerance": 0, "matched": report["ego_entrance_device"] == expected_device,
         "physical_cause_confirmed": False, "cause_evidence": ["entrance_inventory.json"]},
    ]
    result = {
        "case_id": case_id,
        "measured_values": {"first_ego_entry_frame": report["first_ego_entry_frame"],
                            "other_inside_at_ego_entry": report["other_inside_at_ego_entry"],
                            "stopped_before_entry_observed": report["stopped_before_entry_observed"],
                            "operative_signal_controls_ego_at_entry_observed": entry_control},
        "target_checks": checks, "setup_confirmed": False,
        "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved source assessment; legal and physical review pending",
        "physical_failure_flags": ["Physical sign validity, immediate hazard and cautious conduct unresolved"],
        "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["case"]["recording_description"],
        "recording_evidence": evidence, "source_evidence_hashes": hashes,
        "realized_observables": {},
    }
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    write_result(attempt, result)
    measurement_sources = {name: hashes[name] for name in SOURCES}
    measurements = {
        key: {"value": method(report), "method": method.__name__, "sources": measurement_sources}
        for key, method in (
            ("operative_signal_at_entry", measure_operative_signal_at_entry),
            ("ego_entrance_device", measure_ego_entrance_device),
            ("other_inside_at_entry", measure_other_inside_at_entry),
            ("stopped_before_entry", measure_stopped_before_entry),
        )
    }
    analysis = {"format": "worker-signed-entrance-yield-analysis", "case_id": case_id,
                "source_sha256": hashes, "measurements": measurements,
                "source_observations": report, "physical_checks": result["physical_checks"],
                "legal_conclusion": "unresolved", "analysis_complete": True}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
