"""Build case-specific measurements from a sealed original Native trace.

This source-join report is an engineering diagnostic. Documentary authenticity
and physical camera visibility require separate review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from turn_trace_finalizer import ASSIGNMENT, finalize


def _source(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file() or not path.resolve().is_relative_to(attempt.resolve()):
        raise ValueError("Missing required source: " + name)
    return path


def _hashes(attempt: Path, names: list[str]) -> dict[str, str]:
    return {name: hashlib.sha256(_source(attempt, name).read_bytes()).hexdigest()
            for name in names}


def measure_cab_stand_context(measured: dict, packet: dict) -> dict:
    return {"stand_departure_frame": measured["stand_departure_frame"],
            "sources": {key: measured["context_source_joins"][key]
                        for key in ("cab_license", "stand_designation", "stand_marking",
                                    "designation_provisions", "jurisdiction")}}


def measure_posted_notice_context(measured: dict, packet: dict) -> dict:
    return {"notice_meaning": packet["notice_meaning"],
            "notice_source": measured["context_source_joins"]["posted_notice"]}


def measure_first_intersection_maneuver(measured: dict, packet: dict) -> dict:
    return {key: measured[key] for key in
            ("stand_departure_frame", "first_intersection_entry_frame",
             "first_intersection_exit_frame", "first_junction_road_id",
             "receiving_road_id", "turn_angle_deg",
             "engineering_right_turn_observed")}


def analyze(attempt: Path, output: Path) -> dict:
    names = ("reviewed-context.json", "original-trace.jsonl",
             "original-trace-seal.json")
    paths = {name: _source(attempt, name) for name in names}
    packet = json.loads(paths["reviewed-context.json"].read_text())
    case_id = packet.get("case_id", "")
    case = case_id.removeprefix(ASSIGNMENT + "__")
    if (case_id != ASSIGNMENT + "__" + case or case not in
            ("near_stand", "far_stand", "near_stand_straight")):
        raise ValueError("Unknown exact case in reviewed context")
    root = Path(__file__).resolve().parent
    measured = finalize(paths["original-trace.jsonl"],
                        paths["original-trace-seal.json"],
                        paths["reviewed-context.json"],
                        root / "candidates" / (case + ".xodr"),
                        root / "candidates" / (case + ".json"), attempt)
    requirements = (
        ("cab_stand_context", measure_cab_stand_context,
         ["reviewed-context.json", "original-trace.jsonl", "original-trace-seal.json"]),
        ("posted_notice_context", measure_posted_notice_context,
         ["reviewed-context.json"]),
        ("first_intersection_maneuver", measure_first_intersection_maneuver,
         ["reviewed-context.json", "original-trace.jsonl", "original-trace-seal.json"]),
    )
    report = {"format": "c150530-saved-case-analysis-v1", "case_id": case_id,
              "measurements": {key: {"method": method.__name__,
                                     "value": method(measured, packet),
                                     "sources": _hashes(attempt, inputs)}
                               for key, method, inputs in requirements},
              "limitation": "Synthetic CPU attempts do not establish original documentary or physical truth"}
    if output.name != "analysis-report.json":
        raise ValueError("Analysis output must be analysis-report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _joined(attempt: Path, name: str, frames: list[dict]) -> list[dict]:
    rows = _rows(_source(attempt, name))
    if (len(rows) != len(frames) or
            any(row.get("frame") != frame["frame"] or
                abs(row.get("time_s", -1) - frame["time_s"]) > 1e-5
                for row, frame in zip(rows, frames))):
        raise ValueError("Saved frame/time join differs: " + name)
    return rows


def saved_result(attempt: Path, report: dict) -> dict:
    """Write channels and Native-shaped result from retained attempt sources."""
    from worker_exchange.native_output import physical_result, validate_result

    attempt = attempt.resolve()
    config = json.loads(_source(attempt, "config.json").read_text())
    construction = json.loads(_source(attempt, "construction.json").read_text())
    case_id = report["case_id"]
    if (config.get("selected_case_id") != case_id or
            construction.get("case_id") != case_id or
            config.get("case", {}).get("recording_description") !=
            construction.get("recording_description")):
        raise ValueError("Saved result differs from exact construction")
    description = construction["recording_description"]
    originals = _rows(_source(attempt, "original-trace.jsonl"))
    trace = _joined(attempt, "trace.jsonl", originals)
    controls = _joined(attempt, "taxi-controller-history.jsonl", originals)
    mapping = _rows(_source(attempt, "video_frames.jsonl"))
    if (len(mapping) != len(originals) or
            any(row.get("carla_frame") != frame["frame"] or
                row.get("video_frame") != index or
                abs(row.get("time_s", -1) - frame["time_s"]) > 1e-5
                for index, (row, frame) in enumerate(zip(mapping, originals)))):
        raise ValueError("Saved camera frame map differs from original trace")
    videos = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
              "driver_reference.mkv")
    video_hashes = _hashes(attempt, list(videos))
    context = json.loads(_source(attempt, "reviewed-context.json").read_text())
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    values = {
        "original_motion": originals,
        "controller_history": controls,
        "camera_frame_map": mapping,
    }
    for video in videos:
        values[video.removesuffix(".mkv") + "_rgb"] = [
            {"frame": row["carla_frame"], "time_s": row["time_s"],
             "video_frame": row["video_frame"], "source_video": video,
             "source_sha256": video_hashes[video]} for row in mapping]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("Unsupported recording channel: " + name)
        target = channels / (name + ".jsonl")
        with target.open("x") as stream:
            for row in values[name]:
                stream.write(json.dumps({"time_s": row["time_s"], "value": row},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": target.relative_to(attempt).as_posix()})
    joined = report["measurements"]["cab_stand_context"]["value"]["sources"]
    notice = report["measurements"]["posted_notice_context"]["value"]["notice_source"]
    contexts = {name: joined[name] if name in joined else notice
                for name in (item["name"] for item in description["context_inputs"])}
    context_path = channels / "source_context.json"
    context_path.write_text(json.dumps(contexts, indent=2) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": context_path.relative_to(attempt).as_posix()})
    maneuver = report["measurements"]["first_intersection_maneuver"]["value"]
    requested = not case_id.endswith("__near_stand_straight")
    observed = maneuver["engineering_right_turn_observed"]
    target = {"target": "right turn at first post-stand intersection",
              "requested": requested, "measured": observed,
              "method": "sealed original road transition and heading measurement",
              "tolerance": 0, "matched": requested == observed,
              "physical_cause_confirmed": False,
              "cause_evidence": report["measurements"]["first_intersection_maneuver"]["sources"]}
    result = {"case_id": case_id, "measured_values": maneuver,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source assessment pending",
              "physical_failure_flags": {"detection_validated": False},
              "trace_reference": "trace.jsonl", "video_references": list(videos),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    target_path = attempt / "result.json"
    with target_path.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def finalize_attempt(attempt: Path, output: Path) -> tuple[dict, dict]:
    report = analyze(attempt, output)
    return report, saved_result(attempt, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize_attempt(args.attempt, args.output)


if __name__ == "__main__":
    main()
