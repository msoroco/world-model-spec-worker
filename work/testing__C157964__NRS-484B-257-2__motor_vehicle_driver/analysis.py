"""Saved-only original officer-intersection finalizer.

The requested officer gesture and counterpart station never substitute for
original readback. Independent original video review remains a separate source.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from officer_motion import measure
from officer_scene import CASES
from officer_site_packet import validate_packet

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build(attempt: Path) -> tuple[dict, dict]:
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    construction = json.loads(required(attempt, "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("selected original officer construction differs")
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    case = next((item for item in CASES if item.suffix == suffix), None)
    if case is None:
        raise ValueError("unsupported exact officer case")
    seal = json.loads(required(attempt, "capture-seal.json").read_text())
    diagnostic = seal.get("diagnostic_fixture") is True
    count = seal.get("frame_count")
    if seal.get("case_id") != case_id or (not (8 <= count <= 20 or count == 900) if diagnostic and type(count) is int else count != 900):
        raise ValueError("original officer capture seal identity/count differs")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("original officer capture lifecycle incomplete")
    inventory = seal.get("source_sha256")
    if not isinstance(inventory, dict):
        raise ValueError("original officer source inventory missing")
    for name, digest in inventory.items():
        if _sha(required(attempt, name)) != digest:
            raise ValueError("sealed original source changed: " + name)
    site_path = required(attempt, "original-attempt/site-packet.json")
    site = validate_packet(site_path, case_id)
    history = json.loads(required(attempt, "original-attempt/history.json").read_text())
    frames = json.loads(required(attempt, "original-attempt/frame-map.json").read_text())
    traces = _read_lines(required(attempt, "trace.jsonl"))
    video_frames = _read_lines(required(attempt, "video_frames.jsonl"))
    if not all(len(x) == count for x in (history, frames, traces, video_frames)):
        raise ValueError("original frame history/trace/video join incomplete")
    for index, (row, mapped, trace, video) in enumerate(
            zip(history, frames, traces, video_frames)):
        frame, time_s = row.get("frame"), row.get("time_s")
        if row.get("case_id") != case_id or mapped != {
                "frame": index, "carla_frame": frame,
                "elapsed_s": index / 20, "time_s": time_s} or \
                trace.get("frame") != frame or trace.get("time_s") != time_s or \
                video.get("video_frame") != index or \
                video.get("carla_frame") != frame or video.get("time_s") != time_s:
            raise ValueError("original officer frame/trace/video identity differs")
    for name in VIEWS:
        path = attempt / "original-attempt" / (name + ".zip")
        if path.is_file():
            archive_bytes = path.read_bytes()
        elif diagnostic:
            archive_bytes = base64.b64decode(required(
                attempt, "original-attempt/" + name + ".zip.b64").read_text().strip(),
                validate=True)
        else:
            raise ValueError("Missing required source: original-attempt/" + name + ".zip")
        if not diagnostic and inventory.get("original-attempt/" + name + ".zip") != \
                hashlib.sha256(archive_bytes).hexdigest():
            raise ValueError("sealed original camera changed: " + name)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            expected = [f"{i:04d}-{row['frame']}.png" for i, row in enumerate(history)]
            if archive.namelist() != expected:
                raise ValueError("original camera/frame inventory differs: " + name)
            for row, member in zip(history, expected):
                raw = archive.read(member)
                if not raw.startswith(b"\x89PNG\r\n\x1a\n") or \
                        hashlib.sha256(raw).hexdigest() != row["camera_frames"][name]["sha256"]:
                    raise ValueError("original camera PNG changed: " + name)
    review = json.loads(required(attempt, "original-attempt/officer-review.json").read_text())
    video_sha = _sha(required(attempt, "raw.mkv"))
    if review.get("case_id") != case_id or \
            (not diagnostic and review.get("raw_video_sha256") != video_sha) or \
            not review.get("reviewer_id"):
        raise ValueError("independent officer review provenance missing")
    if review.get("source_kind") != (
            "synthetic_review" if diagnostic else "original_independent_review"):
        raise ValueError("independent original officer review required")
    if review.get("officer_visible") is not True or \
            review.get("officer_controlling_traffic") is not True or \
            review.get("observed_directive") != case.officer_directive:
        raise ValueError("active visible officer directive not independently confirmed")
    interval = review.get("crossing_interval_frames")
    if not isinstance(interval, list) or len(interval) != 2 or \
            not all(type(x) is int for x in interval) or \
            not 0 <= interval[0] <= interval[1] < count:
        raise ValueError("reviewed original crossing interval missing")
    measured = measure(history, site, case, diagnostic_fixture=diagnostic)
    if not interval[0] <= measured["first_original_entry_frame"] - history[0]["frame"] <= interval[1]:
        raise ValueError("original officer review/crossing interval differs")
    sources = {name: digest for name, digest in inventory.items() if name in (
        "original-attempt/history.json", "original-attempt/frame-map.json",
        "original-attempt/site-packet.json")}
    sources["original-attempt/officer-review.json"] = _sha(
        required(attempt, "original-attempt/officer-review.json"))
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("refusing to overwrite prior original officer channels")
    channels.mkdir()
    channel_values = {
        "officer_control": lambda row: row["state"]["officer"]["controls_traffic"],
        "officer_directive": lambda row: row["state"]["officer_directive"],
        "ego_entry": lambda row: row["state"]["ego"]["leading_station_m"],
        "ego_speed": lambda row: row["state"]["ego"]["speed_mps"],
        "other_phase": lambda row: row["state"]["other"]["phase"],
        "other_station": lambda row: row["state"]["other"]["center_station_m"],
        "across_or_within": lambda row: row["state"]["ego"]["across_or_within"],
        "entrance_controls": lambda row: site["entrances"],
    }
    description = construction["recording_description"]
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["time_s"],
                                            "value": channel_values[name](row)},
                                           sort_keys=True) + "\n" for row in history))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = channels / "context.json"
    context.write_text(json.dumps({"reviewed_officer_site_packet": {
        "sha256": _sha(site_path), "independent_review_sha256": sources[
            "original-attempt/officer-review.json"]}}, sort_keys=True) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(attempt))})
    value = {"motion": measured, "legal_judgment": "unresolved"}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "analysis_complete": True, "legal_verdict_claimed": False,
              "measurements": {
                  "officer_exception_context": {
                      "value": {"officer_visible": review["officer_visible"],
                                "officer_controlling_traffic": review["officer_controlling_traffic"],
                                "observed_directive": review["observed_directive"],
                                "legal_judgment": None},
                      "method": "build", "sources": sources},
                  "officer_intersection_motion": {
                      "value": value, "method": "build", "sources": sources}},
              "limitations": ["Original officer control and body motion remain subject to local physical review; no legal hazard threshold is inferred."]}
    result = {"case_id": case_id, "measured_values": value,
              "target_checks": [{"target": "original active officer and counterpart phase",
                                 "requested": config["case"]["draft_variables"],
                                 "measured": measured, "method": "saved original source measurement",
                                 "tolerance": None, "matched": False,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": sources}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "original physical and legal review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description,
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": "synthetic_fixture" if diagnostic else "native",
              "diagnostic_fixture": diagnostic,
              "physical_acceptance_claimed": False}
    return report, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    if args.output.exists():
        raise ValueError("refusing to overwrite original officer analysis report")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
