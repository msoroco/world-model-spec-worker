"""Saved-only source-bound turn-signal finalizer for one exact case."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from signal_measure import measure
from source_audit import audit
from signal_controller import TARGETS_FT


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified(root: Path, acquisition: dict, name: str) -> Path:
    path = root / name
    declaration = acquisition.get(name, {})
    if not path.is_file() or declaration.get("kind") != "original_native":
        raise ValueError("Missing required source: " + name)
    if _sha(path) != declaration.get("sha256"):
        raise ValueError("stale original Native source: " + name)
    return path


def build_report(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text())
    case_id = config["selected_case_id"]
    provenance_path = root / "fixture-provenance.json"
    diagnostic = False
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text())
        diagnostic = (provenance.get("diagnostic_fixture") is True and
                      provenance.get("physical_acceptance_claimed") is False)
        if not diagnostic:
            raise ValueError("untrusted diagnostic fixture provenance")
    if diagnostic:
        if not (root / "original-turn-signal.json").is_file():
            raise ValueError("Missing required source: original-turn-signal.json")
        packet = json.loads((root / "original-turn-signal.json").read_text())
        if packet.get("source_kind") != "diagnostic_fixture" or packet.get("case_id") != case_id:
            raise ValueError("Missing required source: exact diagnostic signal samples")
        needed = ("original-site.json", "original-turn-signal.json", "trace.jsonl",
                  "video_frames.jsonl", "body_history.jsonl", "road.xodr",
                  "overview.mkv", "approach.mkv", "reference_corner.mkv",
                  "driver_reference.mkv")
        for name in needed:
            if not (root / name).is_file():
                raise ValueError("Missing required source: " + name)
        acquisition = {name: {"sha256": _sha(root / name), "kind": "diagnostic_fixture"}
                       for name in needed}
        source = {"format": "turn-signal-diagnostic-source-audit",
                  "diagnostic_fixture": True, "frame_count": len(packet["samples"]),
                  "site_sha256": _sha(root / "original-site.json"),
                  "source_decode_passed": True, "physical_acceptance_claimed": False}
    else:
        acquisition = json.loads((root / "acquisition.json").read_text())
        for name in ("original-site.json", "original-turn-signal.json",
                     "original-acquisition-receipt.json", "trace.jsonl",
                     "video_frames.jsonl", "body_history.jsonl", "road.xodr",
                     "carla_recorder.log", "overview.mkv", "approach.mkv",
                     "reference_corner.mkv", "driver_reference.mkv"):
            _verified(root, acquisition, name)
        source = audit(root, case_id)
    measured = measure(root / "original-turn-signal.json", case_id)
    packet = json.loads((root / "original-turn-signal.json").read_text())
    site = json.loads((root / "original-site.json").read_text())
    rows = packet["samples"]
    tag = case_id.rsplit("__", 1)[-1]
    expected_weather = "rain" if tag == "business_weather_rain" else "clear"
    if {row.get("weather") for row in rows} != {expected_weather}:
        raise ValueError("selected original or diagnostic weather history differs")
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if (len(mapping) != len(rows) or any(
            row["frame"] != frame.get("carla_frame") or
            abs(row["time_s"] - frame.get("time_s", float("inf"))) > 1e-4 or
            frame.get("video_frame") != index
            for index, (row, frame) in enumerate(zip(rows, mapping)))):
        raise ValueError("original signal and video frame joins differ")
    if tag not in TARGETS_FT:
        raise ValueError("unselected signal case")
    reference = measured["statutory_reference_ft"]
    distance = measured["continuous_distance_ft"]
    if tag.endswith("_short"):
        matched = distance < reference
    elif "_at_" in tag:
        matched = distance >= reference
    else:
        matched = distance > reference
    matched = matched and not measured["interruption_frames_after_activation"]
    site_sources = {"original-site.json": _sha(root / "original-site.json")}
    signal_sources = {"original-turn-signal.json": _sha(root / "original-turn-signal.json"),
                      "video_frames.jsonl": _sha(root / "video_frames.jsonl")}
    weather_sources = {"original-turn-signal.json": signal_sources["original-turn-signal.json"]}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"signal_distance_measurement": {
                "value": measured, "method": "build_report", "sources": signal_sources},
                "site_context_measurement": {"value": {"site": site,
                    "source_audit": source}, "method": "build_report", "sources": site_sources},
                "weather_independence_measurement": {"value": {
                    "selected_weather": expected_weather,
                    "observed_weather_states": sorted(set(row.get("weather") for row in rows)),
                    "law_rule_weather_independent": True},
                    "method": "build_report", "sources": weather_sources}},
            "selected_target_matched": matched,
            "site": {"map_name": site["map_name"], "site_sha256": source["site_sha256"],
                     "district_review": site["district_review"]},
            "source_decode_passed": True, "analysis_complete": True,
            "diagnostic_fixture": diagnostic,
            "legal_verdict_claimed": False,
            "limitations": ["Authored district and loading-zone sources require independent physical and statutory review.",
                            "Observed signal distance is a 20 Hz sampled lower bound; requested onset is not evidence.",
                            "Original camera source decode does not establish visible signal, district, or physical acceptance."]}


def saved_result(root: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    packet = json.loads((root / "original-turn-signal.json").read_text())
    site = json.loads((root / "original-site.json").read_text())
    rows = packet["samples"]
    streams = {
        "native_frame": [row["frame"] for row in rows],
        "ego_xy": [[row["x_m"], row["y_m"]] for row in rows],
        "right_signal": [row["right_signal"] for row in rows],
        "course_change": [row["course_change"] for row in rows],
        "weather": [row["weather"] for row in rows],
        "four_camera_frames": [row["camera_frames"] for row in rows],
    }
    output = root / "channels"
    output.mkdir(exist_ok=False)
    evidence = []
    description = construction["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unsupported declared signal channel: " + name)
        path = output / (name + ".jsonl")
        with path.open("x") as stream:
            for row, value in zip(rows, streams[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    context = {"highway": site["highway_source"],
               "district_frontage_and_use": {
                   "district_source": site["district_source"],
                   "frontage_source": site["frontage_source"],
                   "building_use_source": site["building_use_source"],
                   "review": site["district_review"]},
               "freight_loading_zone": site["freight_zone_source"],
               "driver_and_vehicle": {"driver_source": site["driver_source"],
                                      "blueprint_id": site["ego_blueprint_id"]}}
    context_path = output / "context.json"
    context_path.write_text(json.dumps(context, sort_keys=True) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(root))})
    measured = report["measurements"]["signal_distance_measurement"]["value"]
    target = {"target": "source-measured selected signal attempt",
              "requested": config["case"]["target"], "measured": {
                  "continuous_distance_ft": measured["continuous_distance_ft"],
                  "interruption_frames": measured["interruption_frames_after_activation"]},
              "method": "saved 20 Hz source measurement", "tolerance": 0,
              "matched": report["selected_target_matched"],
              "physical_cause_confirmed": False,
              "cause_evidence": report["measurements"]["signal_distance_measurement"]["sources"]}
    result = {"case_id": config["selected_case_id"], "measured_values": measured,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original source assessment pending physical review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(root, result)
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.attempt)
    report = build_report(root)
    result = saved_result(root, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    with (root / "result.json").open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    with Path(args.output).open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
