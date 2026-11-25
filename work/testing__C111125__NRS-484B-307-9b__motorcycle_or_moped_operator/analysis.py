"""Saved-only source measurements for the C111125 straight motorcycle cases.

The original event packet is joined to the sealed site and independently
decoded four-camera acquisition. No simulator action or legal label occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_measurement import process_saved


def _need(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_stream(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def measure_actor(site, events, observation, measured, saved):
    return {"actor_id": events[0]["actor_id"], "blueprint_id": events[0]["actor_type_id"],
            "classification_source": site["ego_classification_source"]}


def measure_head(site, events, observation, measured, saved):
    return {"official_head_id": site["official_head_id"],
            "initial_aspects": events[0]["lit_aspects"],
            "observed_frames": len(events)}


def measure_stop(site, events, observation, measured, saved):
    return {"stop_reference_kind": observation["stop_reference_kind"],
            "stop_reference_station_m": observation["stop_reference_station_m"],
            "stopped_frame": observation["stopped_frame"],
            "entry_frame": observation["entry_frame"]}


def measure_cycles(site, events, observation, measured, saved):
    return {"full_cycles_after_stop": observation["full_cycles_after_stop"],
            "cycle_frame_bounds_before_entry": observation["cycle_frame_bounds_before_entry"]}


def measure_cause(site, events, observation, measured, saved):
    return {"classification": observation["unchanged_signal_cause"],
            "cause_source_ref": observation["cause_source_ref"],
            "source_established": observation["unchanged_signal_cause"] != "not_established"}


def measure_participants(site, events, observation, measured, saved):
    return {"regions": measured["participant_regions_observed"],
            "lawful_status": "unresolved", "original_frame_count": len(events)}


def measure_media(site, events, observation, measured, saved):
    return {"views": sorted(saved["camera_views"]),
            "decoded_frames_each": {name: view["decoded_frames"]
                                    for name, view in saved["camera_views"].items()},
            "same_frame_history": len(events)}


ROWS = (("motorcycle_actor", measure_actor), ("official_composite_head", measure_head),
        ("source_ranked_stop", measure_stop), ("complete_cycles", measure_cycles),
        ("unchanged_signal_cause", measure_cause),
        ("participant_yield_context", measure_participants),
        ("synchronized_four_view_media", measure_media))


def analyze(root):
    root = Path(root).resolve()
    config = json.loads(_need(root, "config.json").read_text(encoding="utf-8"))
    site = json.loads(_need(root, "native-site.json").read_text(encoding="utf-8"))
    saved = json.loads(_need(root, "saved-manifest.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if case_id != site.get("case_id") or case_id != saved.get("case_id"):
        raise ValueError("Exact original case identity changed")
    measured = process_saved(site, root, saved, root / "saved-measurement.json")
    events = json.loads(_need(root, "original-events.json").read_text(encoding="utf-8"))
    mapping = [json.loads(line) for line in _need(root, "video_frames.jsonl").read_text().splitlines()]
    if len(events) != len(mapping) or len(events) != 900 or any(
            event["frame"] != frame["carla_frame"] or
            abs(event["time_s"] - frame["time_s"]) > 1e-6 or
            frame["video_frame"] != i
            for i, (event, frame) in enumerate(zip(events, mapping))):
        raise ValueError("Original event/camera frame join differs")
    trace = [json.loads(line) for line in _need(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != len(events) or any(
            trace[i]["frame"] != event["frame"] or
            abs(trace[i]["time_s"] - event["time_s"]) > 1e-6
            for i, event in enumerate(events)):
        raise ValueError("Original Core/event frame join differs")
    observation = measured["measurement"]
    from worker_exchange.native_output import provenance_record, write_result
    provenance = provenance_record(root)
    values = {
        "motorcycle_actor_id": events[0]["actor_id"],
        "first_stop_frame": observation["stopped_frame"],
        "intersection_entry_frame": observation["entry_frame"],
        "full_cycles_after_stop": observation["full_cycles_after_stop"],
        "cycle_frame_bounds_before_entry": observation["cycle_frame_bounds_before_entry"],
        "unchanged_signal_cause": observation["unchanged_signal_cause"],
        "stop_reference_kind": observation["stop_reference_kind"],
        "stop_reference_station_m": observation["stop_reference_station_m"],
        "participant_regions_observed": measured["participant_regions_observed"],
        "lawful_participant_status": "unresolved",
    }
    source_names = ("native-site.json", "saved-manifest.json", "original-events.json",
                    "video_frames.jsonl", "trace.jsonl", "media-receipt.json")
    sources = {name: _sha(_need(root, name)) for name in source_names}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "analysis_complete": True,
              "measurements": {key: {"method": method.__name__,
                                      "value": method(site, events, observation, measured, saved),
                                      "sources": sources}
                               for key, method in ROWS},
              "provenance_kind": provenance["provenance_kind"],
              "diagnostic_fixture": provenance["diagnostic_fixture"],
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
              "limitations": ["Original lawful-status, device causality and pixel visibility need independent review."]}
    channels = config["case"]["recording_description"]["channels"]
    if len(channels) != 7:
        raise ValueError("Recording channel inventory differs")
    def channel_value(index, event, frame):
        if index == 0:
            return {"actor_id": event["actor_id"], "actor_type_id": event["actor_type_id"]}
        if index == 1:
            return {"official_head_id": event["official_head_id"],
                    "lit_aspects": event["lit_aspects"]}
        if index == 2:
            return {"ego_front_station_m": event["ego_front_station_m"],
                    "stop_reference_station_m": site["stop_reference_station_m"],
                    "speed_mps": event["speed_mps"]}
        if index == 3:
            return {"lit_aspects": event["lit_aspects"], "frame": event["frame"]}
        if index == 4:
            return {"cause_classification": site.get("unchanged_signal_cause"),
                    "cause_source_ref": site.get("cause_source_ref")}
        if index == 5:
            return event["other_users"]
        return frame
    evidence = []
    for index, channel in enumerate(channels):
        name = "recording-channel-" + str(index) + ".jsonl"
        _write_stream(root / name, [{"time_s": event["time_s"],
                                     "value": channel_value(index, event, frame)}
                                    for event, frame in zip(events, mapping)])
        evidence.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": name})
    context = config["case"]["recording_description"]["context_inputs"][0]
    context_name = "recording-site-context.json"
    _write_json(root / context_name, {context["name"]: sources})
    evidence.append({"name": context["name"], "unit": context["unit"],
                     "reference": context_name})
    planned = config["case_parameters"]
    checks = [("cycle_count", planned["full_cycles_after_stop_target"],
               observation["full_cycles_after_stop"]),
              ("stop_pattern", planned["stop_pattern"],
               "stopped" if observation["stopped_frame"] is not None else "rolling"),
              ("cause_source", planned["unchanged_signal_cause_target"],
               observation["unchanged_signal_cause"]),
              ("participant_region", planned["other_user_region_at_entry"],
               measured["other_user_region"])]
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [{"target": name, "requested": requested,
                                  "measured": actual, "method": "sealed original event/site join",
                                  "tolerance": 0, "matched": requested == actual,
                                  "physical_cause_confirmed": False,
                                  "cause_evidence": "independent original-source review pending"}
                                 for name, requested, actual in checks],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "saved-only source measurement; physical completion unverified",
              "physical_failure_flags": ["physical_completion_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": provenance["provenance_kind"],
              "diagnostic_fixture": provenance["diagnostic_fixture"],
              "legal_verdict_claimed": False, "physical_acceptance_claimed": False}
    write_result(root, result)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Analysis output already exists")
    _write_json(output, report)
    print(json.dumps({"case_id": report["case_id"],
                      "measurements": len(report["measurements"])}))


if __name__ == "__main__":
    main()
