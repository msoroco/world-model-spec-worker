"""Saved-only source-bound turn-signal finalizer for one exact case."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from signal_measure import measure
from source_audit import audit


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
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if (len(mapping) != len(rows) or any(
            row["frame"] != frame.get("carla_frame") or
            abs(row["time_s"] - frame.get("time_s", float("inf"))) > 1e-4 or
            frame.get("video_frame") != index
            for index, (row, frame) in enumerate(zip(rows, mapping)))):
        raise ValueError("original signal and video frame joins differ")
    tag = case_id.rsplit("__", 1)[-1]
    if tag in ("continuous100", "rain"):
        matched = measured["sampled_threshold_reached"] and not measured["interruption_frames_after_activation"]
    elif tag == "above101":
        matched = measured["continuous_distance_ft"] > 101 and not measured["interruption_frames_after_activation"]
    elif tag == "short80":
        matched = measured["continuous_distance_ft"] < 100 and not measured["interruption_frames_after_activation"]
    elif tag == "interrupted":
        matched = bool(measured["interruption_frames_after_activation"]) and not measured["sampled_threshold_reached"]
    else:
        raise ValueError("unselected signal case")
    sources = {name: acquisition[name]["sha256"] for name in acquisition}
    sources.update({name + ".png.zip": value["sha256"]
                    for name, value in packet["camera_archives"].items()})
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"signal_distance_measurement": {
                "value": measured, "method": "measure", "sources": sources},
                "signal_source_decode_measurement": {"value": source,
                    "method": "independent_source_audit", "sources": sources}},
            "selected_target_matched": matched,
            "site": {"map_name": site["map_name"], "site_sha256": source["site_sha256"],
                     "business_district_review": site["business_district_review"]},
            "source_decode_passed": True, "analysis_complete": True,
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
               "business_district_frontage_and_use": {
                   "district_source": site["district_source"],
                   "frontage_source": site["frontage_source"],
                   "building_use_source": site["building_use_source"],
                   "review": site["business_district_review"]},
               "freight_loading_zone": site["loading_zone_source"],
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
