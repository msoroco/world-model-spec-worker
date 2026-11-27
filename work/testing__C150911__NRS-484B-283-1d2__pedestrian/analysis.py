"""Saved-only original countdown crossing finalizer; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from countdown_crossing import CASES, measure_original

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE = "original-countdown-observations.json"
RECEIPT = "original-countdown-receipt.json"


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measure_flashing_countdown(measured: dict) -> dict:
    return {key: measured[key] for key in (
        "signal_form", "entry_original_frame", "first_zero_original_frame")}


def measure_crossing_completion(measured: dict) -> dict:
    return {key: measured[key] for key in (
        "completion_original_frame", "first_zero_original_frame")}


def measure_zero_boundary(measured: dict) -> dict:
    return {"completion_relation": measured["completion_relation"],
        "completion_original_frame": measured["completion_original_frame"],
        "first_zero_original_frame": measured["first_zero_original_frame"]}


def measure_crossing_context(measured: dict) -> dict:
    return {"crossing_direction": measured["crossing_direction"],
        "exception_applicability": "unresolved"}


def analyze(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    case_id = config.get("selected_case_id")
    case = next((item for item in CASES if case_id.endswith("__" + item.case_id)), None)
    if case is None or (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-283-1d2", "C150911", "pedestrian"):
        raise ValueError("selected countdown case identity differs")
    source = required(attempt, SOURCE)
    packet = json.loads(source.read_text())
    receipt = json.loads(required(attempt, RECEIPT).read_text())
    if (packet.get("assignment_id") != "testing__C150911__NRS-484B-283-1d2__pedestrian" or
            packet.get("case_id") != case_id or receipt.get("case_id") != case_id or
            receipt.get("source_sha256") != sha(source) or receipt.get("fps") != 20 or
            not packet.get("original_trace_id")):
        raise ValueError("original countdown source receipt identity or hash differs")
    measured = measure_original(packet.get("frames"), packet.get("site"), case)
    frame_map = lines(required(attempt, "video_frames.jsonl"))
    trace = lines(required(attempt, "trace.jsonl"))
    frames = packet["frames"]
    if (receipt.get("frame_count") != len(frames) or len(frame_map) != len(frames) or
            len(trace) != len(frames)):
        raise ValueError("original countdown frame stream lengths differ")
    if packet.get("diagnostic_fixture") is False and packet["original_trace_id"] != "Native:" + sha(attempt / "trace.jsonl"):
        raise ValueError("original countdown trace source differs")
    for index, (frame, mapped, native) in enumerate(zip(frames, frame_map, trace)):
        if (mapped.get("video_frame") != index or
                mapped.get("carla_frame") != frame["original_frame"] or
                mapped.get("native_frame") != frame["original_frame"] or
                native.get("frame") != frame["original_frame"] or
                abs(mapped.get("time_s", -1) - frame["time_s"]) > .0001 or
                abs(native.get("time_s", -1) - frame["time_s"]) > .0001 or
                len(native.get("position_m", [])) != 3 or
                len(frame.get("position_m", [])) != 3 or
                any(abs(a - b) > .001 for a, b in zip(
                    native["position_m"], frame["position_m"]))):
            raise ValueError("original countdown frame/time join differs")
    for camera in CAMERAS:
        required(attempt, camera + ".mkv")
    description = config["case"]["recording_description"]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    functions = {
        "signal_countdown": lambda f: {key: f[key] for key in (
            "signal_form", "illuminated", "flashing", "countdown_present",
            "countdown_value", "signal_facing_direction")},
        "pedestrian_crossing": lambda f: {"pedestrian_xy": f["pedestrian_xy"],
            "original_frame": f["original_frame"]},
        "highway_context": lambda f: {"one_way": True,
            "highway_source_sha256": packet["site"]["highway_source_sha256"]},
        "exception_context": lambda f: f["exception_context"],
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in functions:
            raise ValueError("unimplemented countdown channel: " + name)
        reference = "channels/" + name + ".jsonl"
        with (attempt / reference).open("x") as stream:
            for frame in frames:
                stream.write(json.dumps({"time_s": frame["time_s"],
                    "value": functions[name](frame)}, separators=(",", ":")) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": reference})
    context = "channels/reviewed_countdown_site.json"
    (attempt / context).write_text(json.dumps({"reviewed_countdown_site": {
        "highway_source_sha256": packet["site"]["highway_source_sha256"],
        "signal_source_sha256": packet["site"]["signal_source_sha256"],
        "exception_context_source_sha256": packet["site"]["exception_context_source_sha256"],
        "legal_review": "pending"}}) + "\n")
    evidence.append({"name": "reviewed_countdown_site", "unit": "source",
        "reference": context})
    native = {"case_id": case_id, "measured_values": {"countdown_crossing": measured},
        "target_checks": [{"target": "original crossing completion relative to displayed zero",
            "requested": True, "measured": True, "method": "measure_original",
            "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": [SOURCE]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original source measurement; physical/legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}}
    (attempt / "result.json").write_text(json.dumps(native, indent=2, allow_nan=False) + "\n")
    bindings = {SOURCE: sha(source), RECEIPT: sha(attempt / RECEIPT)}
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {
            "flashing_countdown": {"method": "measure_flashing_countdown", "sources": bindings,
                "value": measure_flashing_countdown(measured)},
            "crossing_completion": {"method": "measure_crossing_completion", "sources": bindings,
                "value": measure_crossing_completion(measured)},
            "zero_boundary": {"method": "measure_zero_boundary", "sources": bindings,
                "value": measure_zero_boundary(measured)},
            "crossing_context": {"method": "measure_crossing_context", "sources": bindings,
                "value": measure_crossing_context(measured)}},
        "limitations": ["Actual pixels, signal legibility and referenced exceptions require independent original review."]}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
