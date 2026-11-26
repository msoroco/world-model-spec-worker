"""Saved-only exact driveway measurement and pinned result projection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from driveway_measurements import measure


SOURCES = ("original-attempt/reviewed-context.json", "original-attempt/body-control-trace.jsonl",
           "original-attempt/capture-receipt.json", "road.xodr")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure_driveway_position(attempt, case_id, *, diagnostic=False):
    source = [required(attempt, name) for name in SOURCES]
    return measure(case_id, *source, diagnostic=diagnostic)


def build(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    receipt = json.loads(required(attempt, "original-attempt/capture-receipt.json").read_text())
    marker = attempt / "fixture-provenance.json"
    diagnostic = marker.is_file()
    if diagnostic:
        provenance = json.loads(marker.read_text())
        if provenance.get("diagnostic_fixture") is not True or provenance.get("physical_acceptance_claimed") is not False:
            raise ValueError("untrusted driveway diagnostic marker")
    elif (receipt.get("source_kind") != "original_native_capture" or
          receipt.get("restoration_verified") is not True or
          not (attempt / "capture-seal.json").is_file()):
        raise ValueError("sealed original Native driveway attempt required")
    measurement = measure_driveway_position(attempt, config["selected_case_id"], diagnostic=diagnostic)
    frames = rows(required(attempt, "video_frames.jsonl"))
    generic_trace = rows(required(attempt, "trace.jsonl"))
    body = rows(required(attempt, "original-attempt/body-control-trace.jsonl"))
    if (len(frames) != len(generic_trace) or len(frames) != len(body) or
            any(video.get("video_frame") != i or video.get("carla_frame") != sample.get("carla_frame") or
                generic_trace[i].get("frame") != video.get("carla_frame")
                for i, (video, sample) in enumerate(zip(frames, body)))):
        raise ValueError("original driveway body/Core/video frame identity join differs")
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    value = {"minimum_full_footprint_to_mouth_m": measurement["minimum_observed_full_footprint_to_mouth_m"],
             "maximum_full_footprint_to_mouth_m": measurement["maximum_observed_full_footprint_to_mouth_m"],
             "settled_activity": measurement["activity_window"]["state"],
             "settled_frames": measurement["activity_window"]["frame_count"],
             "driveway_kind": measurement["driveway_kind"],
             "frontage_judgment": None, "necessity_judgment": None,
             "private_relationship_judgment": None, "postal_exception_judgment": None}
    report = {"format": "worker-analysis-report", "analysis_complete": True,
              "measurements": {"driveway_position_measurement": {
                  "value": value, "method": "measure_driveway_position", "sources": source_hashes}},
              "legal_verdict_claimed": False,
              "limitations": ["Five-foot full-footprint mouth distance is an engineering proxy.",
                              "Original frontage, necessity, relationship, postal facts and pixels require review."]}
    return report, measurement, frames


def save_result(attempt, report, measurement, frames):
    from worker_exchange.native_output import validate_result
    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    diagnostic = measurement["diagnostic_fixture"]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    value = report["measurements"]["driveway_position_measurement"]["value"]
    body_rows = rows(attempt / "original-attempt/body-control-trace.jsonl")
    source_context = json.loads((attempt / "original-attempt/reviewed-context.json").read_text())
    channel_values = {
        "full_vehicle_footprint_to_driveway_mouth": [row["full_footprint_to_mouth_m"]
             for row in measurement["observations"]],
        "settled_stop_stand_or_park_activity": [
             {"state": row["control_state"], "speed_mps": row["speed_mps"]} for row in body_rows],
        "driveway_and_exception_context": [source_context] * len(frames)}
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for frame, observed in zip(frames, channel_values[name]):
                stream.write(json.dumps({"time_s": frame["time_s"], "value": observed}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = channels / "context.json"
    context.write_text(json.dumps({"reviewed_driveway_packet": {
        "context_sha256": sha(attempt / SOURCES[0]),
        "review_status": "diagnostic_fixture" if diagnostic else "pending independent review"}}) + "\n")
    for item in construction["recording_description"]["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(attempt))})
    distance = value["minimum_full_footprint_to_mouth_m"]
    position = config["position_target"]
    matched = ((position == "front" and distance <= .05) or
               (position == "within_5ft" and 0 < distance < 1.524) or
               (position == "outside_5ft" and distance > 1.524))
    source_hashes = report["measurements"]["driveway_position_measurement"]["sources"]
    def check(status, method):
        return {"status": status, "method": method, "sources": source_hashes,
                "details": {"diagnostic_fixture": diagnostic}, "missing_evidence": [],
                "legal_verdict_claimed": False, "physical_causation_claimed": False}
    result = {"case_id": config["selected_case_id"], "measured_values": value,
              "target_checks": [{"target": "full vehicle footprint distance to reviewed driveway mouth",
                                 "requested": position, "measured": distance,
                                 "method": "measure_driveway_position", "tolerance": 0,
                                 "matched": matched, "physical_cause_confirmed": False,
                                 "cause_evidence": source_hashes}],
              "setup_confirmed": True, "behavior_attempted": True,
              "maneuver_completed": matched,
              "termination_reason": "Original physical and legal driveway review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": {"full_footprint_mouth_distance_m": {
                  "value": distance, "unit": "m", "method": "saved original full footprint to surveyed mouth",
                  "time_window": "settled activity", "statistic": "minimum",
                  "reference": SOURCES[1]}},
              "physical_checks": {"setup": check("met", "source-joined map, body and camera inventory"),
                                  "target": check("met" if matched else "not_met", "saved full-footprint distance"),
                                  "maneuver": check("met" if matched else "not_met",
                                                    "source-joined sustained activity and full footprint target")},
              "provenance_kind": "synthetic_fixture" if diagnostic else "native",
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False}
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report, measurement, frames = build(args.attempt)
    result = save_result(args.attempt, report, measurement, frames)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    if (args.attempt / "result.json").exists() or args.output.exists():
        raise ValueError("retain prior saved driveway analysis")
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
