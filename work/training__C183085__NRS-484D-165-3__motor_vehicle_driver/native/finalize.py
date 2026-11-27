"""Finalize saved shoulder lamp sources; never infer a legal verdict."""
import argparse
import json
import subprocess
from pathlib import Path

from saved_shoulder import join, rows, sha

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("shoulder-lamp-trace.jsonl", "video_frames.jsonl",
           "shoulder_lighting_survey.json", "optical_measurements.json")
CHANNELS = ("drv.standing_or_parked", "st.shoulder", "rel.occupies",
            "drv.civil_night", "env.visibility", "sig.position_lamp",
            "sig.headlamp", "rel.bearing", "st.lane", "st.roadway")


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


def measurement_source(attempt, measurement):
    return {name: sha(Path(attempt) / name) for name in SOURCES}


def measure_selected_requirement(attempt, config, measurement):
    kind = config["optical_target_kind"]
    value = ({"position_omission_frames": len(
                 measurement["position_command_omission_frames"]),
              "low_beam_omission_frames": len(
                 measurement["low_beam_command_omission_frames"])}
             if kind == "none" else measurement["optical_brackets"][kind])
    return {"value": value, "method": "measure_selected_requirement",
            "sources": measurement_source(attempt, measurement),
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def emit_channels(attempt, config, measurement):
    trace = rows(Path(attempt) / "shoulder-lamp-trace.jsonl")
    survey = json.loads((Path(attempt) / "shoulder_lighting_survey.json").read_text())
    optics = json.loads((Path(attempt) / "optical_measurements.json").read_text())
    channels = {name: [] for name in CHANNELS}
    for row in trace:
        values = {"drv.standing_or_parked": {"speed_mps": row["ego_speed_mps"],
                                            "state": "stopped_sample"},
                  "st.shoulder": {"survey_source": survey["adjacent_paved_shoulder_source"]},
                  "rel.occupies": {"surveyed_shoulder_pose": survey.get("shoulder_xyz_m")},
                  "drv.civil_night": {"clock_source": survey["civil_time_source"],
                                      "lighting_hours_source": survey["lighting_hours_source"]},
                  "env.visibility": {"ambient_reveal_probe":
                                     measurement["optical_brackets"]["ambient_reveal"]},
                  "sig.position_lamp": {"commanded": row["position_commanded"],
                                        "front_color_verified": False,
                                        "rear_color_verified": False},
                  "sig.headlamp": {"low_beam_commanded": row["low_beam_commanded"]},
                  "rel.bearing": {"passing_traffic_side": survey["passing_traffic_side"],
                                  "near_side_installation_verified": False},
                  "st.lane": {"source": survey["passing_lane_source"]},
                  "st.roadway": {"source": survey["highway_identity_source"]}}
        for name, value in values.items():
            channels[name].append({"time_s": row["time_s"], "value": value})
    channel_dir = Path(attempt) / "channels"
    channel_dir.mkdir(exist_ok=False)
    for name, values in channels.items():
        (channel_dir / (name + ".jsonl")).write_text(
            "".join(json.dumps(value, separators=(",", ":")) + "\n" for value in values))
    (channel_dir / "shoulder_lighting_survey.json").write_text(
        json.dumps({"shoulder_lighting_survey": survey,
                    "optical_measurements_source_kind": optics["source_kind"]}) + "\n")
    return [{"name": item["name"], "unit": item["unit"],
             "reference": "channels/" + item["name"] + ".jsonl"}
            for item in config["recording_description"]["channels"]] + [
            {"name": "shoulder_lighting_survey", "unit": "structured",
             "reference": "channels/shoulder_lighting_survey.json"}]


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use fresh saved attempt; original sources are immutable")
    if not (attempt / "config.json").is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads((attempt / "config.json").read_text())
    if (config.get("frames"), config.get("rate_hz"), config.get("duration_s")) != \
            (600, 20, 30):
        raise ValueError("Exact 600-frame capture changed")
    survey = json.loads((attempt / "shoulder_lighting_survey.json").read_text())
    fixture = survey.get("source_kind") == "synthetic_native_sample"
    measurement = join(attempt, config, allow_fixture=fixture)
    trace, evidence = rows(attempt / "trace.jsonl"), rows(attempt / "capture/evidence.jsonl")
    source = rows(attempt / "shoulder-lamp-trace.jsonl")
    if any(len(row) != 600 for row in (trace, evidence, source)):
        raise ValueError("Complete original trace and capture evidence absent")
    for joined, original, sample in zip(source, trace, evidence):
        native = joined["native_frame"]
        if original.get("frame") != native or sample.get("original_frame") != native or \
                abs(original.get("time_s", -1) - joined["time_s"]) > .001 or \
                abs(sample.get("recording_time_s", -1) - joined["time_s"]) > .001:
            raise ValueError("Original trace and capture evidence join differs")
    videos = {name + ".mkv": decoded_frames(attempt / (name + ".mkv"))
              for name in CAMERAS}
    if any(count != 600 for count in videos.values()):
        raise ValueError("Four-camera 600-frame source incomplete")
    description = config["recording_description"]
    if {item["name"] for item in description["channels"]} != set(CHANNELS):
        raise ValueError("Recording description changed shoulder lamp channels")
    refs = emit_channels(attempt, config, measurement)
    target_kind = config["optical_target_kind"]
    if target_kind == "none":
        requested = {"lamp_command": config["lamp_command"]}
        measured = {"position_omission_frames": len(
            measurement["position_command_omission_frames"])}
        matched = (not measured["position_omission_frames"] if
                   config["lamp_command"] == "display" else
                   measured["position_omission_frames"] == 600)
        tolerance = 0
    else:
        requested = config["target_distance_ft"]
        bracket = measurement["optical_brackets"][target_kind]
        measured = bracket["estimate_ft"]
        tolerance = bracket["uncertainty_ft"]
        matched = abs(requested - measured) <= tolerance
    result = {"case_id": config["case_id"],
              "measured_values": {"optical_brackets": measurement["optical_brackets"],
                                  "lamp_command_omission_frames": len(
                                      measurement["position_command_omission_frames"])},
              "target_checks": [{"target": "requested lamp or optical source shape",
                                 "requested": requested,
                                 "measured": measured,
                                 "method": "original independent optical protocol and pixels",
                                 "tolerance": tolerance,
                                 "matched": matched,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(measurement["source_hashes"])}],
              "setup_confirmed": False, "behavior_attempted": not fixture,
              "maneuver_completed": False,
              "termination_reason": "full saved 600-frame shoulder lamp source analyzed",
              "physical_failure_flags": ["optical_pixels_and_near_side_review_required"] +
                                        (["synthetic_fixture_not_physical"] if fixture else []),
              "trace_reference": "trace.jsonl", "video_references": list(videos),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": refs,
              "realized_observables": {}, "physical_checks": {"shoulder_lamp": measurement},
              "provenance_kind": "synthetic_cpu_fixture" if fixture else "native",
              "accepted": False, "legal_verdict_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result, write_result
    result = physical_result(attempt, result)
    result["physical_observations"]["shoulder_lamp"] = measurement
    validate_result(result)
    report = {"format": "worker-c183085-saved-shoulder-lamp-analysis-v1",
              "case_id": config["case_id"], "measurements": {
                  {"none": "shoulder_lamp_display", "ambient_reveal": "ambient_reveal_ft",
                   "front_white_or_amber": "front_visibility_ft",
                   "rear_red": "rear_visibility_ft"}[config["optical_target_kind"]]:
                      measure_selected_requirement(attempt, config, measurement)},
              "source_join": measurement,
              "source_hashes": measurement_source(attempt, measurement),
              "four_camera_frames": videos, "actual_pixels_review_required": True,
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
