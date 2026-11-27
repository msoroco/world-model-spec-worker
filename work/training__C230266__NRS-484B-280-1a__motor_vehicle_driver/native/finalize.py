"""Finalize saved pedestrian encounter sources without deciding statutory due care."""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from saved_due_care import join, rows, sha

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
MEASUREMENT_SOURCES = ("pedestrian-due-care-trace.jsonl", "video_frames.jsonl",
                       "contact_events.jsonl", "road_survey.json")


def decoded_frames(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    process = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                              "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                              "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                             capture_output=True, text=True, timeout=120)
    if process.returncode or not process.stdout.strip().isdigit():
        raise ValueError("Four-camera decode failed: " + path.name)
    return int(process.stdout.strip())


def source_hashes(attempt, names):
    root = Path(attempt)
    for name in names:
        if not (root / name).is_file():
            raise ValueError("Missing required source: " + name)
    return {name: sha(root / name) for name in names}


def measure_driver_source(attempt, config, packet, measurement):
    return {"value": "motor_vehicle_driver",
            "method": "measure_driver_source",
            "sources": source_hashes(attempt, ("pedestrian-due-care-trace.jsonl", "road_survey.json")),
            "legal_verdict_claimed": False}


def measure_pedestrian_encounter(attempt, config, packet, measurement):
    return {"value": measurement["minimum_surface_gap_m"],
            "method": "measure_pedestrian_encounter",
            "sources": source_hashes(attempt, MEASUREMENT_SOURCES),
            "diagnostics": measurement, "legal_verdict_claimed": False}


def measure_person_afoot(attempt, config, packet, measurement):
    return {"value": packet["pedestrian_classification_source"],
            "method": "measure_person_afoot",
            "sources": source_hashes(attempt, ("road_survey.json", "pedestrian-due-care-trace.jsonl")),
            "actual_pixels_review_required": True}


def channel_rows(packet):
    output = {name: [] for name in ("ru.pedestrian", "drv.time_to_conflict",
              "rel.contact", "rel.surface_gap", "kin.speed", "drv.hard_deceleration",
              "drv.vulnerable_road_user", "native_source_join")}
    prior_speed = None
    for row in packet["trace"]:
        dx = row["pedestrian_x_m"] - row["vehicle_x_m"]
        dy = row["pedestrian_y_m"] - row["vehicle_y_m"]
        gap = max(0.0, math.hypot(dx, dy) - row["vehicle_radius_m"] - row["pedestrian_radius_m"])
        closing = row["vehicle_speed_mps"] - row["pedestrian_speed_mps"]
        ttc = dx / closing if dx > 0 and closing > 0 and row["path_conflict_survey"] else None
        decel = None if prior_speed is None else (prior_speed - row["vehicle_speed_mps"]) * 20
        prior_speed = row["vehicle_speed_mps"]
        values = {"ru.pedestrian": {"actor_id": packet["pedestrian_id"],
                                     "classification_source": packet["pedestrian_classification_source"]},
                  "drv.time_to_conflict": {"defined": ttc is not None, "seconds": ttc},
                  "rel.contact": row["contact_sensor"],
                  "rel.surface_gap": gap,
                  "kin.speed": row["vehicle_speed_mps"],
                  "drv.hard_deceleration": {"defined": decel is not None,
                                             "deceleration_mps2": decel},
                  "drv.vulnerable_road_user": {"actor_id": packet["pedestrian_id"],
                                               "class": "person_afoot"},
                  "native_source_join": {"native_frame": row["native_frame"],
                                         "video_frame": row["video_frame"]}}
        for name, value in values.items():
            output[name].append({"time_s": row["time_s"], "value": value})
    return output


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved attempt; original sources are immutable")
    if not (attempt / "config.json").is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads((attempt / "config.json").read_text())
    if config.get("duration_s") != 30 or config.get("rate_hz") != 20 or \
            config.get("frames") != 600:
        raise ValueError("Exact 600-frame capture changed")
    if not (attempt / "road_survey.json").is_file():
        raise ValueError("Missing required source: road_survey.json")
    survey = json.loads((attempt / "road_survey.json").read_text())
    fixture = survey.get("source_kind") == "synthetic_native_sample"
    packet, measurement = join(attempt, config["case_id"], allow_fixture=fixture)
    if (config["controller"] == "maintain_request" and measurement["requested_brake_frames"] != 0) or \
            (config["controller"] == "distance_triggered_slow_request" and
             measurement["requested_brake_frames"] == 0):
        raise ValueError("Original requested control differs from selected comparison condition")
    trace, evidence = rows(attempt / "trace.jsonl"), rows(attempt / "capture/evidence.jsonl")
    if any(len(source) != 600 for source in (trace, evidence)):
        raise ValueError("Complete original trace and capture evidence absent")
    for joined, original, sample in zip(packet["trace"], trace, evidence):
        native = joined["native_frame"]
        if original.get("frame") != native or sample.get("original_frame") != native or \
                abs(original.get("time_s", -1) - joined["time_s"]) > .001 or \
                abs(sample.get("recording_time_s", -1) - joined["time_s"]) > .001:
            raise ValueError("Original trace and capture evidence join differs")
    videos = {name + ".mkv": decoded_frames(attempt / (name + ".mkv")) for name in CAMERAS}
    if any(count != 600 for count in videos.values()):
        raise ValueError("Four-camera 600-frame source incomplete")
    description = config["recording_description"]
    channels = channel_rows(packet)
    if {item["name"] for item in description["channels"]} != set(channels):
        raise ValueError("Recording description changed due-care channels")
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=False)
    for name, values in channels.items():
        (channel_dir / (name + ".jsonl")).write_text(
            "".join(json.dumps(value, separators=(",", ":")) + "\n" for value in values))
    (channel_dir / "pedestrian_path_survey.json").write_text(
        json.dumps({"pedestrian_path_survey": survey}) + "\n")
    refs = [{"name": item["name"], "unit": item["unit"],
             "reference": "channels/" + item["name"] + ".jsonl"}
            for item in description["channels"]]
    refs += [{"name": "pedestrian_path_survey", "unit": "structured",
              "reference": "channels/pedestrian_path_survey.json"}]
    result = {"case_id": config["case_id"],
              "measured_values": {"minimum_surface_gap_m": measurement["minimum_surface_gap_m"],
                                  "contact_frames": measurement["contact_frames"],
                                  "minimum_nonnegative_time_to_conflict_s": measurement["minimum_nonnegative_time_to_conflict_s"],
                                  "peak_measured_deceleration_mps2": measurement["peak_measured_deceleration_mps2"]},
              "target_checks": [{"target": "source-observed pedestrian encounter response",
                                 "requested": config["controller"],
                                 "measured": measurement["requested_brake_frames"],
                                 "method": "source-bound original pose, contact and requested control join",
                                 "tolerance": None, "matched": None,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(packet["source_hashes"])}],
              "setup_confirmed": False, "behavior_attempted": not fixture,
              "maneuver_completed": False,
              "termination_reason": "full saved 600-frame pedestrian encounter analyzed",
              "physical_failure_flags": ["pedestrian_path_motion_and_pixels_review_required"] +
                                        (["synthetic_fixture_not_physical"] if fixture else []),
              "trace_reference": "trace.jsonl", "video_references": list(videos),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": refs,
              "realized_observables": {}, "physical_checks": {"due_care_diagnostics": measurement},
              "provenance_kind": "synthetic_cpu_fixture" if fixture else "native",
              "accepted": False, "legal_verdict_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result, write_result
    result = physical_result(attempt, result)
    result["physical_observations"]["due_care_diagnostics"] = measurement
    validate_result(result)
    report = {"format": "worker-c230266-saved-due-care-analysis-v1",
              "case_id": config["case_id"],
              "measurements": {
                  "driver_source": measure_driver_source(attempt, config, packet, measurement),
                  "pedestrian_encounter_gap": measure_pedestrian_encounter(attempt, config, packet, measurement),
                  "person_afoot_source": measure_person_afoot(attempt, config, packet, measurement)},
              "source_hashes": packet["source_hashes"], "four_camera_frames": videos,
              "actual_pixels_review_required": True,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    write_result(attempt, result)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(finalize(arguments.attempt, arguments.output), sort_keys=True))
