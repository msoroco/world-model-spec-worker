"""Saved-only measurements for the NRS 484B.710 fire-apparatus branches.

This module reads original capture files. It never treats a commanded distance,
warning device, or synthetic context as an observed legal outcome.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


def _load_sibling(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


branch_measurement = _load_sibling("fire_branch")


def required_source(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    raw = path.read_bytes()
    if not raw:
        raise ValueError("Empty required source: " + name)
    return path, sha256(raw).hexdigest()


def _rows(path):
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise ValueError("Invalid original frame map or trace") from error


def _original_frames(root):
    mapping_path, mapping_hash = required_source(root, "video_frames.jsonl")
    trace_path, trace_hash = required_source(root, "trace.jsonl")
    mapping, trace = _rows(mapping_path), _rows(trace_path)
    if not mapping or len(mapping) != len(trace):
        raise ValueError("Original trace/frame-map length differs")
    previous = None
    for index, (frame, row) in enumerate(zip(mapping, trace)):
        identity = (frame.get("carla_frame"), frame.get("time_s"))
        if (frame.get("video_frame") != index or row.get("frame") != identity[0]
                or row.get("time_s") != identity[1]
                or type(identity[0]) is not int
                or (previous is not None and (identity[0] <= previous[0]
                                             or identity[1] <= previous[1]))):
            raise ValueError("Original trace/frame-map join failed")
        previous = identity
    return mapping, {"video_frames.jsonl": mapping_hash, "trace.jsonl": trace_hash}


def measure_fire_branch(root, config, context):
    """Measure selected branch from the original synchronized geometry/state."""
    root = Path(root)
    mapping, frame_sources = _original_frames(root)
    participants, _ = required_source(root, "participant_footprints.jsonl")
    states, _ = required_source(root, "participant_state.jsonl")
    measured = branch_measurement.measure_branch(
        participants, states, len(mapping), config["fire_branch"], context)
    source_rows = branch_measurement._read_jsonl(participants, "participant footprint")[0]
    state_rows = branch_measurement._read_jsonl(states, "participant state")[0]
    for frame, footprint, state in zip(mapping, source_rows, state_rows):
        identity = (frame["carla_frame"], frame["time_s"])
        if ((footprint.get("frame"), footprint.get("time_s")) != identity
                or (state.get("frame"), state.get("time_s")) != identity):
            raise ValueError("Original fire source/frame-map join failed")
    sources = {**frame_sources,
               "participant_footprints.jsonl": measured["participant_source_sha256"],
               "participant_state.jsonl": measured["state_source_sha256"]}
    return measured, sources


def measure_alarm_context(context):
    """Retain the cited dispatch premise separately from warning readbacks."""
    return {"alarm_response_source": context["alarm_response_source"],
            "apparatus_answered_alarm": context["apparatus_answered_alarm"]}


def measure_exception_context(context):
    """Retain authorization and official-business premises separately."""
    return {"subject_authorized_emergency": context["subject_authorized_emergency"],
            "subject_official_business": context["subject_official_business"]}


def analyze(attempt, *, write_channel=True):
    root = Path(attempt)
    config_path, _ = required_source(root, "config.json")
    context_path, context_hash = required_source(root, "fire_context.json")
    config, context = json.loads(config_path.read_text()), json.loads(context_path.read_text())
    if config.get("law_id") != "NRS-484B-710" or not config.get("selected_case_id"):
        raise ValueError("Wrong fire-law case identity")
    measured, sources = measure_fire_branch(root, config, context)
    # This converter-facing stream is rebuilt from retained original geometry
    # after capture. It is never accepted as an independently acquired source.
    channel = root / "fire_gap_ft.jsonl"
    if write_channel:
        channel.write_text("".join(json.dumps({"time_s": row["time_s"],
                                                "value": row["nearest_footprint_gap_ft"],
                                                "frame": row["frame"]}) + "\n"
                                   for row in measured["observations"]))
    sources["fire_context.json"] = context_hash
    return {"format": "worker-analysis-report", "case_id": config["selected_case_id"],
            "measurements": {
                "fire_boundary_observation": {"method": "measure_fire_branch", "value": measured,
                                              "sources": sources},
                "alarm_context": {"method": "measure_alarm_context",
                                  "value": measure_alarm_context(context),
                                  "sources": {"fire_context.json": context_hash}},
                "exception_context": {"method": "measure_exception_context",
                                      "value": measure_exception_context(context),
                                      "sources": {"fire_context.json": context_hash}}},
            "limitations": ["Original-frame software measurement only; fire-alarm purpose and authorization are sourced premises, and physical visibility requires review."],
            "legal_acceptance_claimed": False, "physical_acceptance_claimed": False}


def build_result(attempt, report):
    """Build a conservative Native-shaped result from measured saved sources."""
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    case = config.get("case", {})
    description = case.get("recording_description")
    if not isinstance(description, dict):
        raise ValueError("Missing selected recording description")
    observed = report["measurements"]["fire_boundary_observation"]["value"]
    boundary = observed["boundary_measurement"]
    return {
        "case_id": report["case_id"],
        "measured_values": {"fire_boundary_observation": observed},
        "target_checks": [{"target": "500 ft source measurement",
                           "requested": config.get("target_distance_ft", 500),
                           "measured": observed["min_boundary_distance_ft"],
                           "method": "minimum original active-frame " + boundary,
                           "tolerance": None, "matched": False,
                           "physical_cause_confirmed": False,
                           "cause_evidence": "Original footprint/state samples; requested equality and physical realization require review"}],
        "setup_confirmed": False,
        "behavior_attempted": observed["active_frame_count"] > 0,
        "maneuver_completed": False,
        "termination_reason": "Saved source measurement complete; physical completion unverified",
        "physical_failure_flags": {"detection_validated": False},
        "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv",
                             "reference_corner.mkv", "driver_reference.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": [{"name": "fire_gap_ft", "unit": "ft",
                                "reference": "fire_gap_ft.jsonl",
                                "sha256": sha256((root / "fire_gap_ft.jsonl").read_bytes()).hexdigest()}],
        "realized_observables": {"fire_gap_ft": {
            "unit": "ft", "method": "ground-footprint nearest separation from retained Native corners",
            "time_window": "all original frames", "statistic": "min",
            "reference": "fire_gap_ft.jsonl", "value": observed["min_gap_ft"],
            "sample_window_s": [observed["observations"][0]["time_s"],
                                observed["observations"][-1]["time_s"]]}},
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior analysis report; choose fresh output")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == "__main__":
    main()
