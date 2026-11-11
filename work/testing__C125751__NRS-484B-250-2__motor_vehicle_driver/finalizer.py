"""Saved-only C125751 signal, body-entry and stop-order analysis."""
import argparse
import hashlib
import json
from pathlib import Path

from entry_measurements import analyze as measure_entry
from signal_measurements import analyze as measure_signal
from stop_measurements import analyze as measure_stop

PREFIX = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__"
CASES = {PREFIX + "signal_operative": "Green", PREFIX + "signal_off": "Off"}
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
REQUIRED = ("config.json", "road_geometry.json", "crossing_history.jsonl", "signal_context.json",
            "signal_history.jsonl", "head_visibility_review.json", "other_head_visibility_review.json", "stop_context.json",
            "stop_history.jsonl", "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl", *CAMERAS)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _lines(rows):
    return "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)


def analyze_sources(attempt):
    entry = measure_entry(attempt)
    if not all(entry["first_body_entry"].values()):
        raise ValueError("Both original vehicle body entries required")
    signal = measure_signal(attempt, entry)
    stop = measure_stop(attempt, entry)
    return entry, signal, stop


def finalize(attempt: Path, output: Path):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior finalization; choose a fresh attempt")
    for name in REQUIRED:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("selected_case_id")
    if case not in CASES or config.get("law_id") != "NRS-484B-250-2" or config.get("cell_id") != "C125751":
        raise ValueError("Exact C125751 signal case required")
    if config.get("target_signal_state") != CASES[case]:
        raise ValueError("Exact case target signal state required")
    if not isinstance(config.get("recording_description"), dict):
        raise ValueError("Recording description required")
    entry, signal, stop = analyze_sources(attempt)
    measured_state = signal["at_body_entry"]["ego"]["native_state"]
    channels = attempt / "channels"
    channels.mkdir()
    signal_rows = [json.loads(line) for line in (attempt / "signal_history.jsonl").read_text().splitlines() if line.strip()]
    stop_rows = [json.loads(line) for line in (attempt / "stop_history.jsonl").read_text().splitlines() if line.strip()]
    (channels / "signal_state.jsonl").write_text(_lines({"time_s": row["time_s"],
        "value": {"frame": row["frame"], "native_state": row["state"],
                  "native_signal_id": row["native_signal_id"],
                  "other_native_state": row["other_state"],
                  "other_native_signal_id": row["other_native_signal_id"]}} for row in signal_rows))
    (channels / "stop_state.jsonl").write_text(_lines({"time_s": row["time_s"],
        "value": {"frame": row["frame"], "ego": row["ego"], "other": row["other"]}}
        for row in stop_rows))
    context = {"entry_context": {"first_body_entry": entry["first_body_entry"],
        "entry_delta_s": entry["ego_minus_other_entry_time_s"],
        "other_is_to_ego_right": entry["other_is_to_ego_right"],
        "signal_at_entry": signal["at_body_entry"],
        "stop_order": stop,
        "approximately_same_time_judgment": "unresolved; no numeric legal threshold",
        "official_control_judgment": "unresolved",
        "inoperative_judgment": "unresolved"}}
    (channels / "entry_context.json").write_text(json.dumps(context, indent=2, allow_nan=False) + "\n")
    measurements = {
        "body_entry_timing": {"method": "measure_entry", "value": {
            "first_body_entry": entry["first_body_entry"],
            "ego_minus_other_entry_time_s": entry["ego_minus_other_entry_time_s"]},
            "sources": entry["sources"]},
        "signal_at_entry": {"method": "measure_signal", "value": {
            "at_body_entry": signal["at_body_entry"], "head_review": signal["head_review"],
            "other_head_review": signal["other_head_review"],
            "official_control_judgment": signal["official_control_judgment"],
            "inoperative_judgment": signal["inoperative_judgment"]},
            "sources": {**signal["sources"], signal["head_review"]["camera"] + ".mkv": signal["source_video_sha256"],
                        signal["other_head_review"]["camera"] + ".mkv": signal["other_source_video_sha256"]}},
        "stop_order": {"method": "measure_stop", "value": {
            "first_recorded_zero_speed_before_entry": stop["first_recorded_zero_speed_before_entry"],
            "other_body_inside_at_ego_entry": stop["other_body_inside_at_ego_entry"],
            "statutory_stop_judgment": stop["statutory_stop_judgment"],
            "statutory_yield_judgment": stop["statutory_yield_judgment"]},
            "sources": stop["sources"]}}
    matched = measured_state == config["target_signal_state"]
    result = {"case_id": case,
        "measured_values": {"entry_delta_s": entry["ego_minus_other_entry_time_s"],
                            "ego_signal_state_at_entry": measured_state},
        "target_checks": [{"target": "ego_native_signal_state_at_body_entry",
            "requested": config["target_signal_state"], "measured": measured_state,
            "method": "original signal/body/frame join", "tolerance": 0, "matched": matched,
            "physical_cause_confirmed": False,
            "cause_evidence": ["signal_history.jsonl", "crossing_history.jsonl", "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved original-source signal and stop analysis; physical/legal review pending",
        "physical_failure_flags": ["official signal status, uncovered head pixels, statutory inoperability and stop/yield unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "signal_state", "unit": "structured record",
                                "reference": "channels/signal_state.jsonl"},
                               {"name": "stop_state", "unit": "structured record",
                                "reference": "channels/stop_state.jsonl"},
                               {"name": "entry_context", "unit": "structured record",
                                "reference": "channels/entry_context.json"}],
        "source_evidence_hashes": {**entry["sources"], **signal["sources"], **stop["sources"],
                                   signal["head_review"]["camera"] + ".mkv": signal["source_video_sha256"],
                                   signal["other_head_review"]["camera"] + ".mkv": signal["other_source_video_sha256"]},
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({"format": "worker-signal-entry-saved-analysis",
        "case_id": case, "measurements": measurements,
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False},
        indent=2, allow_nan=False) + "\n")
    return measurements


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
