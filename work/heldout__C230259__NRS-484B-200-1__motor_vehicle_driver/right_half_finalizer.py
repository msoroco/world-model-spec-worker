"""Saved-only right-half finalization from original Native road/body sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from right_half_measurement import measure

PREFIX = "heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__"


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError("Missing required source: " + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, *, write_channels=True):
    root = Path(attempt)
    config = json.loads(_required(root, "config.json")[0].read_text())
    case = config.get("selected_case_id")
    if ((config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-200-1", "C230259", "motor_vehicle_driver") or
            not isinstance(case, str) or not case.startswith(PREFIX)):
        raise ValueError("Wrong C230259 exact right-half identity")
    names = ("ego_road_frames.jsonl", "road_exception_context.json",
             "video_frames.jsonl", "trace.jsonl")
    sources = {name: _required(root, name) for name in names}
    value = measure(sources[names[0]][0], sources[names[1]][0])
    road = _rows(sources[names[0]][0])
    mapping = _rows(sources[names[2]][0])
    trace = _rows(sources[names[3]][0])
    if len(road) != len(mapping) or len(road) != len(trace):
        raise ValueError("Original road/frame/trace counts differ")
    for index, (body, frame, packet) in enumerate(zip(road, mapping, trace)):
        identity = body["frame"], body["time_s"]
        if (frame.get("video_frame") != index or
                (frame.get("carla_frame"), frame.get("time_s")) != identity or
                (packet.get("frame"), packet.get("time_s")) != identity):
            raise ValueError("Original road/frame/trace identity join differs")
    if write_channels:
        channel = root / "right_half_observation.jsonl"
        if channel.exists():
            raise ValueError("Retain prior derived right-half channel")
        channel.write_text("".join(json.dumps({
            "frame": row["frame"], "time_s": row["time_s"],
            "value": {"minimum_signed_lateral_m": row["minimum_signed_lateral_m"],
                      "maximum_signed_lateral_m": row["maximum_signed_lateral_m"],
                      "road_width_m": row["road_width_m"]}}, allow_nan=False) + "\n"
            for row in value["observations"]))
    return {"format": "worker-analysis-report", "case_id": case,
            "measurements": {"right_half_observation": {
                "method": "analyze",
                "value": value, "sources": {name: item[1] for name, item in sources.items()}}},
            "limitations": ["Road width and exception premises remain separately reviewed observations; physical completion, camera pixels and legal sufficiency are unverified."],
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    value = report["measurements"]["right_half_observation"]["value"]
    observations = value["observations"]
    channel = "right_half_observation.jsonl"
    evidence = [{"name": "right_half_observation", "unit": "m",
                 "reference": channel, "sha256": _required(root, channel)[1]},
                {"name": "road_exception_context", "unit": "structured context",
                 "reference": "road_exception_context.json",
                 "sha256": _required(root, "road_exception_context.json")[1]}]
    return {"case_id": report["case_id"],
            "measured_values": {"right_half_observation": value},
            "target_checks": [{"target": "full-body position relative to highway right half",
                               "requested": "original directed road and body geometry",
                               "measured": max(row["maximum_signed_lateral_m"] for row in observations),
                               "method": "20 Hz full-body signed lateral extent",
                               "tolerance": None, "matched": False,
                               "physical_cause_confirmed": False,
                               "cause_evidence": "Original source joined; physical and legal outcomes unverified"}],
            "setup_confirmed": False, "behavior_attempted": True,
            "maneuver_completed": False,
            "termination_reason": "Saved road/body measurement complete; physical outcome unverified",
            "physical_failure_flags": {"detection_validated": False},
            "trace_reference": "trace.jsonl",
            "video_references": ["overview.mkv", "approach.mkv",
                                 "reference_corner.mkv", "driver_reference.mkv"],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": config["case"]["recording_description"],
            "recording_evidence": evidence,
            "realized_observables": {"right_half_maximum_lateral_m": {
                "unit": "m", "method": "original full-body directed road geometry",
                "time_window": "all original frames", "statistic": "maximum",
                "reference": channel,
                "value": max(row["maximum_signed_lateral_m"] for row in observations),
                "sample_window_s": [observations[0]["time_s"], observations[-1]["time_s"]]}},
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior right-half analysis report")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))
