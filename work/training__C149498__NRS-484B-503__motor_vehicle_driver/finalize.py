"""Saved-only passenger curb measurement with explicit original-source uncertainty."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from native.loading_scene import CAMERAS, FRAMES
from native.measure_loading_native import measure, sign_effective
from worker_exchange.native_output import physical_result, write_result


def source(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_zone_timing(observation):
    return {"halted_in_marked_segment_frames": observation["halted_in_marked_segment_frames"],
            "effective_sign_hours_frames": observation["effective_sign_hours_frames"],
            "zone_regulatory_authority": observation["zone_regulatory_authority"]}


def measure_passenger_context(observation):
    return {"passenger_near_door_frames": observation["passenger_near_door_frames"],
            "door_open_request_frames": observation["door_open_request_frames"],
            "observed_passenger_doorway_transfer": observation["observed_passenger_doorway_transfer"],
            "occupant_count": observation["occupant_count"],
            "expeditiousness": observation["expeditiousness"]}


def read_rows(root, name):
    return [json.loads(line) for line in source(root, name).read_text().splitlines() if line.strip()]


def inspect_sources(root, context):
    paths = context.get("source_files", {})
    required = {"native_map", "zone", "motion", "ego_body", "passenger_body", "camera_manifest"}
    if set(paths) != required:
        raise ValueError("Original passenger loading source inventory incomplete")
    for key, name in paths.items():
        if sha(source(root, name)) != context.get(key + "_sha256"):
            raise ValueError("Original passenger loading source hash differs: " + key)
    zone = json.loads(source(root, "loading_zone.json").read_text())
    if zone.get("map_readback_sha256") != context["native_map_sha256"]:
        raise ValueError("Original map/zone readback hash differs")
    if zone.get("regulatory_authority_confirmed") is not False:
        raise ValueError("Original regulatory authority was invented")
    return zone


def inspect_video_sources(root, frames):
    if len(frames) != FRAMES:
        raise ValueError("Original four-camera frame map incomplete")
    for name in CAMERAS:
        count = subprocess.check_output(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
             str(source(root, name + ".mkv"))], text=True, timeout=120).strip()
        if count != str(FRAMES):
            raise ValueError("Original source camera full decode differs: " + name)
    for row in frames:
        hashes = row.get("camera_rgb_sha256")
        if (not isinstance(hashes, dict) or set(hashes) != set(CAMERAS) or
                any(not isinstance(value, str) or len(value) != 64 for value in hashes.values())):
            raise ValueError("Original four-camera RGB frame hashes missing")
        if set(row.get("source_cameras", {})) != set(CAMERAS):
            raise ValueError("Original four-camera frame identities missing")
        if any(value != row.get("native_frame") for value in row["source_cameras"].values()):
            raise ValueError("Original four-camera Native frame join differs")


def finalize(attempt, output):
    root = Path(attempt).resolve()
    destination = Path(output)
    if destination.exists():
        raise ValueError("Retain prior selected analysis output")
    config = json.loads(source(root, "config.json").read_text())
    case = config["selected_case_id"]
    context = json.loads(source(root, "loading_context.json").read_text())
    if case != context.get("case_id"):
        raise ValueError("Selected case and original loading context differ")
    kind = context.get("source_kind")
    if kind not in {"original_native_passenger_curb_readback", "synthetic_passenger_curb_fixture"}:
        raise ValueError("Known passenger curb source kind required")
    zone = inspect_sources(root, context)
    motion = read_rows(root, "loading_motion.jsonl")
    bodies = read_rows(root, "ego_body.jsonl")
    passengers = read_rows(root, "passenger_body.jsonl")
    frames = read_rows(root, "video_frames.jsonl")
    trace = read_rows(root, "trace.jsonl")
    inspect_video_sources(root, frames)
    measured = measure(context, zone, motion, bodies, passengers, frames, trace)
    provenance = json.loads(source(root, "acquisition-provenance.json").read_text())
    expected_kind = "native" if kind == "original_native_passenger_curb_readback" else "synthetic_fixture"
    if (provenance.get("provenance_kind") != expected_kind or
            provenance.get("diagnostic_fixture") is not (kind != "original_native_passenger_curb_readback")):
        raise ValueError("Passenger curb acquisition provenance differs")
    channels = root / "channels"
    channels.mkdir(exist_ok=True)
    (channels / "vehicle_zone_motion.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": {
            "vehicle_center_m": row["vehicle_center_m"],
            "vehicle_speed_mps": row["vehicle_speed_mps"],
            "door_open_request_active": row["door_open_request_active"]}},
            allow_nan=False) + "\n" for row in motion))
    (channels / "passenger_body.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": {
            "passenger_center_m": row["passenger_center_m"],
            "actor_id": row["passenger_actor_id"]}}, allow_nan=False) + "\n" for row in motion))
    (channels / "zone_sign.json").write_text(json.dumps({
        "zone_sign": zone, "source_sha256": sha(source(root, "loading_zone.json"))},
        allow_nan=False) + "\n")
    channel_values = {
        "st.curb_zone": lambda row: {"authored_zone_segment_m": [-25, -1],
                                     "vehicle_center_m": row["vehicle_center_m"]},
        "dev.regulatory_sign": lambda row: {"sign_id": zone["sign_id"],
                                           "sign_text_hours": zone["sign_text_hours"],
                                           "regulatory_authority_confirmed": False},
        "drv.condition_in_effect": lambda row: {"signed_hours_effective": sign_effective(row["civil_timestamp"], zone),
                                                "authority_confirmed": False},
        "env.civil_time": lambda row: {"timestamp": row["civil_timestamp"],
                                       "time_zone": zone["time_zone"]},
        "drv.standing_or_parked": lambda row: {"vehicle_speed_mps": row["vehicle_speed_mps"],
                                               "action_legal_classification": "unassessed"},
        "sig.door_open": lambda row: {"door_open_requested": row["door_open_request_active"],
                                      "actual_door_state_observed": False},
        "ru.occupant_count": lambda row: {"occupant_count_observed": False,
                                          "actual_count": "unobserved_pending_original_source"},
        "ru.pedestrian": lambda row: {"passenger_actor_id": row["passenger_actor_id"],
                                      "passenger_center_m": row["passenger_center_m"]},
        "kin.time": lambda row: {"time_s": row["time_s"], "native_frame": row["native_frame"]},
    }
    for name, value in channel_values.items():
        (channels / (name + ".jsonl")).write_text("".join(
            json.dumps({"time_s": row["time_s"], "value": value(row)},
                       allow_nan=False) + "\n" for row in motion))
    context_sources = {"native_map": "road.xodr", "loading_zone": "loading_zone.json",
        "ego_body": "ego_body.jsonl", "passenger_body": "passenger_body.jsonl",
        "camera_manifest": "video_frames.jsonl"}
    for name, filename in context_sources.items():
        (channels / (name + ".json")).write_text(json.dumps({
            name: {"reference": filename, "source_sha256": sha(source(root, filename))}},
            allow_nan=False) + "\n")
    result = {"case_id": case, "measured_values": measured,
        "target_checks": [{"target": "source-bound passenger curb episode",
                           "requested": config.get("passenger_transfer_requested"),
                           "measured": measured["observed_passenger_doorway_transfer"],
                           "method": "original actor body, sign, civil time and four-camera frame join",
                           "tolerance": "none: passenger transfer and expeditiousness require independent original review",
                           "matched": False, "physical_cause_confirmed": False,
                           "cause_evidence": ["loading_motion.jsonl", "ego_body.jsonl",
                                              "passenger_body.jsonl", "loading_zone.json",
                                              "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "600 saved frames measured; passenger transfer and legal review pending",
        "physical_failure_flags": ["actual passenger transfer unconfirmed",
                                   "original zone regulatory authority unverified",
                                   "occupant count not observed by CARLA"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in sorted(CAMERAS)],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [
            {"name": name, "unit": "structured", "reference": "channels/" + name + ".jsonl"}
            for name in channel_values] + [
            {"name": name, "unit": "structured", "reference": "channels/" + name + ".json"}
            for name in context_sources],
        "realized_observables": {}, "provenance_kind": expected_kind,
        "diagnostic_fixture": kind != "original_native_passenger_curb_readback",
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    sources = {name: sha(source(root, filename)) for name, filename in context["source_files"].items()}
    first_inputs = ["loading_zone.json", "loading_motion.jsonl", "ego_body.jsonl",
                    "passenger_body.jsonl", "video_frames.jsonl"]
    shared_sources = {name: sha(source(root, name)) for name in first_inputs}
    payload = {"format": "worker-passenger-curb-selected-measurement", "case_id": case,
        "measurement": measured, "measurements": {
            "zone_timing": {"method": "measure_zone_timing",
                            "value": measure_zone_timing(measured), "sources": shared_sources},
            "passenger_context": {"method": "measure_passenger_context",
                                  "value": measure_passenger_context(measured),
                                  "sources": shared_sources}},
        "source_sha256": sources,
        "actual_passenger_transfer_confirmed": False,
        "zone_regulatory_authority_confirmed": False,
        "legal_compliance": "unassessed", "physical_acceptance_claimed": False}
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), allow_nan=False))
