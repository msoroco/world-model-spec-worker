"""Finalize saved hydrant sources as measurements, without a legal verdict."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_hydrant import join, rows, sha

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("hydrant-trace.jsonl", "video_frames.jsonl", "hydrant_survey.json")


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


def measure_hydrant_clearance(attempt, config, measurement):
    return {"value": measurement["closest_footprint_distance_ft"],
            "method": "measure_hydrant_clearance",
            "sources": source_hashes(attempt, SOURCES),
            "applicable_threshold_ft": measurement["applicable_threshold_ft"],
            "distance_bracket_ft": measurement["distance_bracket_ft"],
            "threshold_relation": measurement["threshold_relation"],
            "paint_or_sign_used_to_select_threshold": False,
            "legal_verdict_claimed": False}


def measure_exception_context(attempt, config, measurement):
    return {"value": measurement["exception_context_declaration"],
            "method": "measure_exception_context",
            "sources": source_hashes(attempt, ("hydrant-trace.jsonl", "hydrant_survey.json")),
            "exception_source_verified": False,
            "legal_verdict_claimed": False}


def channel_rows(attempt, config, measurement):
    trace = rows(Path(attempt) / "hydrant-trace.jsonl")
    survey = json.loads((Path(attempt) / "hydrant_survey.json").read_text())
    names = ("st.fire_hydrant", "rel.centre_distance", "st.parking_space",
             "dev.regulatory_sign", "drv.standing_or_parked", "kin.extent", "st.curb_zone")
    channels = {name: [] for name in names}
    for row in trace:
        values = {"st.fire_hydrant": {"actor_id": row["hydrant_actor_id"],
                                           "source": survey["hydrant_identity_source"]},
                  "rel.centre_distance": {"closest_body_distance_ft":
                      measurement["closest_footprint_distance_ft"],
                      "uncertainty_ft": survey["distance_uncertainty_ft"]},
                  "st.parking_space": {"permission": config["parking_permission"],
                                       "source": survey["parking_permission_source"]},
                  "dev.regulatory_sign": {"permission_source":
                                          survey["parking_permission_source"]},
                  "drv.standing_or_parked": {"speed_mps": row["ego_speed_mps"],
                                            "state": "at_rest"},
                  "kin.extent": {"xyz_m": row["ego_extent_xyz_m"]},
                  "st.curb_zone": {"paint_used_to_select_threshold": False}}
        for name, value in values.items():
            channels[name].append({"time_s": row["time_s"], "value": value})
    return channels


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
    if not (attempt / "hydrant_survey.json").is_file():
        raise ValueError("Missing required source: hydrant_survey.json")
    survey = json.loads((attempt / "hydrant_survey.json").read_text())
    fixture = survey.get("source_kind") == "synthetic_native_sample"
    measurement = join(attempt, config, allow_fixture=fixture)
    trace, evidence = rows(attempt / "trace.jsonl"), rows(attempt / "capture/evidence.jsonl")
    source = rows(attempt / "hydrant-trace.jsonl")
    if any(len(row) != 600 for row in (trace, evidence, source)):
        raise ValueError("Complete original trace and capture evidence absent")
    for joined, original, sample in zip(source, trace, evidence):
        native = joined["native_frame"]
        if original.get("frame") != native or sample.get("original_frame") != native or \
                abs(original.get("time_s", -1) - joined["time_s"]) > .001 or \
                abs(sample.get("recording_time_s", -1) - joined["time_s"]) > .001:
            raise ValueError("Original trace and capture evidence join differs")
    videos = {name + ".mkv": decoded_frames(attempt / (name + ".mkv")) for name in CAMERAS}
    if any(count != 600 for count in videos.values()):
        raise ValueError("Four-camera 600-frame source incomplete")
    description = config["recording_description"]
    channels = channel_rows(attempt, config, measurement)
    if {item["name"] for item in description["channels"]} != set(channels):
        raise ValueError("Recording description changed hydrant channels")
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=False)
    for name, values in channels.items():
        (channel_dir / (name + ".jsonl")).write_text(
            "".join(json.dumps(value, separators=(",", ":")) + "\n" for value in values))
    (channel_dir / "hydrant_parking_survey.json").write_text(
        json.dumps({"hydrant_parking_survey": survey}) + "\n")
    refs = [{"name": item["name"], "unit": item["unit"],
             "reference": "channels/" + item["name"] + ".jsonl"}
            for item in description["channels"]]
    refs.append({"name": "hydrant_parking_survey", "unit": "structured",
                 "reference": "channels/hydrant_parking_survey.json"})
    result = {"case_id": config["case_id"],
              "measured_values": {"closest_hydrant_body_distance_ft":
                                  measurement["closest_footprint_distance_ft"],
                                  "applicable_threshold_ft": measurement["applicable_threshold_ft"]},
              "target_checks": [{"target": "requested hydrant body clearance",
                                 "requested": config["requested_clearance_ft"],
                                 "measured": measurement["closest_footprint_distance_ft"],
                                 "method": "original pose, extent and hydrant survey join",
                                 "tolerance": survey["distance_uncertainty_ft"],
                                 "matched": measurement["requested_target_confirmed"],
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(measurement["source_hashes"])}],
              "setup_confirmed": False, "behavior_attempted": not fixture,
              "maneuver_completed": False,
              "termination_reason": "full saved 600-frame hydrant source analyzed",
              "physical_failure_flags": ["parking_motion_and_pixels_review_required"] +
                                        (["synthetic_fixture_not_physical"] if fixture else []),
              "trace_reference": "trace.jsonl", "video_references": list(videos),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": refs,
              "realized_observables": {}, "physical_checks": {"hydrant_diagnostics": measurement},
              "provenance_kind": "synthetic_cpu_fixture" if fixture else "native",
              "accepted": False, "legal_verdict_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result, write_result
    result = physical_result(attempt, result)
    result["physical_observations"]["hydrant_diagnostics"] = measurement
    validate_result(result)
    report = {"format": "worker-c200568-saved-hydrant-analysis-v1",
              "case_id": config["case_id"],
              "measurements": {
                  "hydrant_clearance_ft": measure_hydrant_clearance(attempt, config, measurement),
                  "exception_context": measure_exception_context(attempt, config, measurement)},
              "source_hashes": measurement["source_hashes"],
              "four_camera_frames": videos,
              "actual_pixels_review_required": True,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    write_result(attempt, result)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
