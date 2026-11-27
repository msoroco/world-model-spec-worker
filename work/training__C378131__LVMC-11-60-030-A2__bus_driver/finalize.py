"""Saved-only bus loading finalizer; source requests are not legal observations."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from analysis.saved_only import extract

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def source(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_covered_bus(readout):
    return {"requested_vehicle_class": readout["vehicle_class_requested"],
            "original_class_provenance": "pending_independent_review"}


def measure_loading_place(readout):
    return {"requested_zone_kind": readout["zone_kind_requested"],
            "stopped_body_in_segment_frames": readout["stopped_body_in_authored_segment_frames_measured"],
            "designation_authority": readout["designation_authority"]}


def measure_exception(readout):
    return {"emergency_requested": readout["emergency_requested"],
            "emergency_facts": readout["emergency_facts"],
            "actual_passenger_transfer": readout["actual_passenger_transfer"]}


def finalize(attempt, output):
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT required before runtime imports")
    root = Path(attempt).resolve()
    output = Path(output)
    if output.exists():
        raise ValueError("retain prior analysis report")
    config = json.loads(source(root, "config.json").read_text())
    context = json.loads(source(root, "bus_context.json").read_text())
    fixture = context.get("source_kind") == "synthetic_native_sample"
    if context.get("source_kind") not in ("original_native_bus_readback", "synthetic_native_sample"):
        raise ValueError("undeclared bus loading source kind")
    if context.get("zone_kind_requested") != config["zone_kind_requested"] or context.get(
            "vehicle_class_requested") != config["vehicle_class_requested"] or context.get(
            "emergency_requested") != config["emergency_requested"]:
        raise ValueError("selected exact case and source context differ")
    readout = extract(root, output, fixture=fixture)
    motion = [json.loads(line) for line in source(root, "bus_motion.jsonl").read_text().splitlines()
              if line.strip()]
    frame_map = [json.loads(line) for line in source(root, "video_frames.jsonl").read_text().splitlines()
                 if line.strip()]
    for name in CAMERAS:
        source(root, name + ".mkv")
    if len(frame_map) != 600 or len(motion) != 600:
        raise ValueError("complete source frame map missing")
    provenance = json.loads(source(root, "acquisition-provenance.json").read_text())
    expected = "synthetic_fixture" if fixture else "native"
    if provenance.get("provenance_kind") != expected or provenance.get("diagnostic_fixture") is not fixture:
        raise ValueError("source acquisition provenance differs")
    channels = root / "channels"
    channels.mkdir(exist_ok=True)
    values = {
        "ru.bus": lambda row: {"bus_actor_id": row["bus_actor_id"],
                               "vehicle_class_requested": readout["vehicle_class_requested"]},
        "ru.tour_bus_or_limousine": lambda row: {"tour_class_requested":
                                                  readout["vehicle_class_requested"] == "tour_bus",
                                                  "original_class_confirmed": False},
        "drv.stopped": lambda row: {"bus_speed_mps": row["bus_speed_mps"]},
        "sig.door_open": lambda row: {"door_open_requested": row["door_open_request_active"],
                                       "actual_door_state_observed": False},
        "ru.occupant_count": lambda row: {"actual_count": None,
                                           "occupant_count_observed": False},
        "ru.pedestrian": lambda row: {"actor_id": row["passenger_actor_id"],
                                        "center_m": row["passenger_center_m"]},
        "st.curb_zone": lambda row: {"zone_kind_requested": readout["zone_kind_requested"],
                                      "designation_authority_confirmed": False},
        "st.transit_stop": lambda row: {"zone_id": context["zone_id"],
                                         "designation_authority_confirmed": False},
        "rel.occupies": lambda row: {"bus_center_m": row["bus_center_m"],
                                      "zone_id": context["zone_id"]},
        "sig.hazard": lambda row: {"mechanical_fault_requested": row[
                                      "mechanical_fault_request_active"],
                                   "emergency_facts_confirmed": False},
    }
    for name, value in values.items():
        (channels / (name + ".jsonl")).write_text("".join(json.dumps({
            "time_s": row["time_s"], "value": value(row)}, allow_nan=False) + "\n"
            for row in motion))
    context_sources = {"native_map": "road.xodr", "motion": "bus_motion.jsonl",
                       "bus_body": "bus_body.jsonl", "passenger_body": "passenger_body.jsonl",
                       "camera_manifest": "video_frames.jsonl"}
    for name, filename in context_sources.items():
        (channels / (name + ".json")).write_text(json.dumps({
            name: {"reference": filename, "source_sha256": sha(source(root, filename))}},
            allow_nan=False) + "\n")
    source_paths = {"text-0": ["bus_context.json", "bus_motion.jsonl", "bus_body.jsonl"],
                    "text-1": ["bus_context.json", "road.xodr", "passenger_body.jsonl",
                               "video_frames.jsonl"],
                    "reviewed-scope-0": ["bus_context.json", "road.xodr", "bus_body.jsonl",
                                         "passenger_body.jsonl"]}
    methods = {"text-0": ("measure_covered_bus", measure_covered_bus),
               "text-1": ("measure_exception", measure_exception),
               "reviewed-scope-0": ("measure_loading_place", measure_loading_place)}
    output_keys = {"text-0": "covered_bus", "text-1": "emergency_and_loading_context",
                   "reviewed-scope-0": "actual_loading_place"}
    measurements = {output_keys[key]: {"method": method[0], "value": method[1](readout),
                          "sources": {name: sha(source(root, name)) for name in source_paths[key]}}
                    for key, method in methods.items()}
    result = {
        "case_id": config["selected_case_id"], "measured_values": readout,
        "target_checks": [{"target": "source-bound bus stop and loading request",
                           "requested": config["zone_kind_requested"],
                           "measured": readout["stopped_body_in_authored_segment_frames_measured"],
                           "method": "original bus body, passenger body, map and four-camera frame join",
                           "tolerance": "engineering segment overlap only; legal designation and actual loading unverified",
                           "matched": False, "physical_cause_confirmed": False,
                           "cause_evidence": ["bus_motion.jsonl", "bus_body.jsonl",
                                              "passenger_body.jsonl", "road.xodr",
                                              "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "saved sources measured; original review pending",
        "physical_failure_flags": ["actual boarding unconfirmed", "designation authority unverified",
                                   "emergency and class need independent source review"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": name, "unit": "structured",
                                "reference": "channels/" + name + ".jsonl"} for name in values] +
                              [{"name": name, "unit": "structured",
                                "reference": "channels/" + name + ".json"} for name in context_sources],
        "realized_observables": {}, "provenance_kind": expected,
        "diagnostic_fixture": fixture, "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False}
    # Runtime imports occur after runtime.py has established its artifact root.
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(root, result)
    write_result(root, result)
    payload = {"format": "worker-bus-loading-selected-measurement",
               "case_id": config["selected_case_id"], "measurements": measurements,
               "source_sha256": readout["source_files_sha256"],
               "physical_acceptance_claimed": False,
               "legal_compliance": "unassessed"}
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), allow_nan=False))
