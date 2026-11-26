"""Finalize saved angle-parking sources after Native ownership ends."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from saved_angle import measure, read_json, read_rows


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoded_frames(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError("Four-camera decode failed: " + path.name)
    return int(result.stdout.strip())


def measure_official_device_angle(attempt, config):
    device = read_json(Path(attempt) / "official_device.json")
    if device.get("official_device_review_required") is not True:
        raise ValueError("Official device source review flag absent")
    return {"value": device["indicated_angle_to_curb_deg"],
            "method": "measure_official_device_angle",
            "sources": {"official_device.json": sha(Path(attempt) / "official_device.json")},
            "actual_sign_pixels_confirmed": False}


def measure_at_rest_angle(attempt, config):
    road = read_json(Path(attempt) / "road_geometry.json")
    fixture = road.get("provenance") == "synthetic_cpu_fixture"
    outcome = measure(attempt, config["case_id"], allow_fixture=fixture)
    return {"value": outcome["mean_measured_angle_to_curb_deg"],
            "method": "measure_at_rest_angle", "sources": outcome["source_hashes"],
            "detail": outcome}


def derive_channels(attempt, config, samples, mapping):
    channels = Path(attempt) / "channels"
    channels.mkdir(exist_ok=True)
    device = read_json(Path(attempt) / "official_device.json")
    road = read_json(Path(attempt) / "road_geometry.json")
    context = read_json(Path(attempt) / "parking_context.json")
    (channels / "context.json").write_text(json.dumps({"official_device": device,
        "road_geometry": road}, indent=2, allow_nan=False) + "\n")
    values = {}
    for name in [entry["name"] for entry in config["recording_description"]["channels"]]:
        values[name] = []
    for sample, frame in zip(samples, mapping):
        row = {
            "dev.regulatory_sign": {"device_id": device["device_id"],
                "indicated_angle_to_curb_deg": device["indicated_angle_to_curb_deg"],
                "actual_pixels_review_required": True},
            "dev.governs": {"space_id": device["governs_space_id"],
                "native_road_id": device["native_road_id"]},
            "st.parking_space": {"space_id": road["space_id"],
                "native_parking_lane_id": road["parking_lane_id"]},
            "drv.standing_or_parked": {"activity": context["activity"],
                "speed_mps": sample["ego_speed_mps"]},
            "kin.heading": sample["ego_heading_deg"],
            "kin.speed": sample["ego_speed_mps"],
            "st.road_edge": {"heading_deg": road["curb_tangent_heading_deg"],
                "side": road["curb_side"]},
            "rel.occupies": {"space_id": sample["space_id"],
                "native_road_id": sample["native_road_id"],
                "native_lane_id": sample["native_lane_id"]},
            "native_body_pose": sample,
            "camera_frame_join": frame,
        }
        for name in values:
            if name not in row:
                raise ValueError("Unsupported recorded channel: " + name)
            values[name].append(json.dumps({"time_s": sample["time_s"],
                "value": row[name]}, allow_nan=False))
    for name, lines in values.items():
        (channels / (name + ".jsonl")).write_text("\n".join(lines) + "\n")


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved attempt; original sources are immutable")
    config = read_json(attempt / "config.json")
    if config.get("duration_s") != 30 or config.get("rate_hz") != 20:
        raise ValueError("Exact 30-second capture changed")
    samples = read_rows(attempt / "native_samples.jsonl")
    mapping = read_rows(attempt / "video_frames.jsonl")
    trace = read_rows(attempt / "trace.jsonl")
    evidence = read_rows(attempt / "capture/evidence.jsonl")
    fixture = read_json(attempt / "road_geometry.json").get("provenance") == "synthetic_cpu_fixture"
    angle = measure(attempt, config["case_id"], allow_fixture=fixture)
    if any(len(items) != 600 for items in (trace, evidence)):
        raise ValueError("Complete original trace/evidence source absent")
    for sample, frame, tr, ev in zip(samples, mapping, trace, evidence):
        native = sample["native_frame"]
        if frame["native_frame"] != native or tr["frame"] != native or \
                ev["original_frame"] != native:
            raise ValueError("Original trace/evidence frame join differs")
        if any(abs(float(t) - sample["time_s"]) > .001 for t in
                (frame["time_s"], tr["time_s"], ev["recording_time_s"])):
            raise ValueError("Original trace/evidence time join differs")
    videos = {name + ".mkv": decoded_frames(attempt / (name + ".mkv"))
              for name in CAMERAS}
    if any(count != 600 for count in videos.values()):
        raise ValueError("Four-camera 600-frame source incomplete")
    description = config["recording_description"]
    derive_channels(attempt, config, samples, mapping)
    refs = [{"name": item["name"], "unit": item["unit"],
             "reference": "channels/" + item["name"] + ".jsonl"}
            for item in description["channels"]]
    refs += [{"name": item["name"], "unit": item["unit"],
              "reference": "channels/context.json"}
             for item in description["context_inputs"]]
    requested = config["parked_heading_request_deg"]
    observed = angle["mean_measured_angle_to_curb_deg"]
    result = {"case_id": config["case_id"],
        "measured_values": {"at_rest_angle_to_curb_deg": observed,
            "maximum_absolute_difference_from_device_deg":
                angle["maximum_absolute_difference_deg"]},
        "target_checks": [{"target": "at-rest angle to curb indicated by official device",
            "requested": requested, "measured": observed,
            "method": "saved original Native body/curb/device source join",
            "tolerance": None, "matched": None,
            "physical_cause_confirmed": False,
            "cause_evidence": list(angle["source_hashes"])}],
        "setup_confirmed": False, "behavior_attempted": not fixture,
        "maneuver_completed": False,
        "termination_reason": "full saved 600-frame window analyzed",
        "physical_failure_flags": ["official_device_and_body_pixel_review_required"] +
            (["synthetic_fixture_not_physical"] if fixture else []),
        "trace_reference": "trace.jsonl", "video_references": list(videos),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": refs,
        "realized_observables": {}, "physical_checks": {"at_rest_angle": angle},
        "provenance_kind": "synthetic_cpu_fixture" if fixture else "native",
        "accepted": False, "legal_verdict_claimed": False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {"format": "c385967-nrs460-saved-analysis-v1",
        "case_id": config["case_id"],
        "measurements": {"official_device_angle": measure_official_device_angle(attempt, config),
            "at_rest_angle_to_curb": measure_at_rest_angle(attempt, config)},
        "source_hashes": angle["source_hashes"], "four_camera_frames": videos,
        "actual_pixels_review_required": True,
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2,
        allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
