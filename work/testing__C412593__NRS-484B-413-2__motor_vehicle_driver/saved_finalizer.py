"""Finalize one saved right-turn attempt from retained original sources."""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from native_sources import CAMERAS, RATE_HZ, SIZES
from turn_signal_measurements import analyze


def _probe(path):
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True)
    if process.returncode:
        raise ValueError("Original camera decode failed: " + path.name)
    streams = json.loads(process.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("Single original camera stream required: " + path.name)
    return streams[0]


def _signed_turn(heading, baseline):
    return (heading - baseline + 180) % 360 - 180


def _validate_course(root, context):
    rows = [json.loads(line) for line in (root / "drive_history.jsonl").read_text().splitlines()
            if line.strip()]
    if len(rows) < 3:
        raise ValueError("Incomplete original course history")
    baseline = rows[0].get("ego_heading_deg")
    if type(baseline) not in (int, float):
        raise ValueError("Missing original Native heading")
    if (rows[0].get("ego_road_id"), rows[0].get("ego_lane_id")) != (
            context["approach_road_id"], context["approach_lane_id"]):
        raise ValueError("Original trace does not begin on sourced approach")
    onset = next((row["frame"] for row in rows
                  if type(row.get("ego_heading_deg")) in (int, float) and
                  _signed_turn(row["ego_heading_deg"], baseline) <= -5), None)
    if onset != context["turn_onset_frame"]:
        raise ValueError("Turn onset differs from original heading trace")
    final = rows[-1]
    if (final.get("ego_road_id"), final.get("ego_lane_id")) != (
            context["outgoing_road_id"], context["outgoing_lane_id"]):
        raise ValueError("Original trace does not reach sourced outgoing lane")
    angle = _signed_turn(final.get("ego_heading_deg", 0), baseline)
    if not -150 < angle < -30:
        raise ValueError("Original heading trace is not a completed right turn")
    return {"turn_onset_frame": onset, "final_heading_change_degrees": angle,
            "outgoing_road_id": final["ego_road_id"],
            "outgoing_lane_id": final["ego_lane_id"]}


def finalize(root, *, diagnostic_fixture=False):
    root = Path(root)
    if type(diagnostic_fixture) is not bool:
        raise ValueError("Explicit diagnostic fixture flag required")
    result = analyze(root)
    context = json.loads((root / "route_context.json").read_text())
    course = _validate_course(root, context)
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()
              if line.strip()]
    if len(frames) < 3 or any(row["video_frame"] != index for index, row in enumerate(frames)):
        raise ValueError("Incomplete original video frame map")
    if not diagnostic_fixture and len(frames) != 45 * RATE_HZ:
        raise ValueError("Full 900-frame original camera duration required")
    previous_time = None
    for row in frames:
        time_s = row.get("time_s")
        if (type(time_s) not in (int, float) or not math.isfinite(time_s) or
                (previous_time is not None and abs(time_s - previous_time - 1 / RATE_HZ) > 1e-3)):
            raise ValueError("Original video frame timing differs from 20 Hz")
        previous_time = time_s
    streams = {}
    for camera in CAMERAS:
        path = root / (camera + ".mkv")
        if not path.is_file():
            raise ValueError("Missing original camera source: " + camera)
        metadata = _probe(path)
        if (metadata.get("codec_name") != "ffv1" or
                metadata.get("r_frame_rate") != str(RATE_HZ) + "/1" or
                int(metadata.get("nb_read_frames", -1)) != len(frames) or
                int(metadata.get("width", 0)) <= 0 or int(metadata.get("height", 0)) <= 0):
            raise ValueError("Original camera source profile/frame count differs: " + camera)
        if not diagnostic_fixture and (metadata["width"], metadata["height"]) != SIZES[camera]:
            raise ValueError("Full original camera dimensions required: " + camera)
        streams[camera] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "codec": "ffv1", "width": metadata["width"],
                           "height": metadata["height"], "frames": len(frames)}
    result["route_turn_direction_judgment"] = "original heading/road trace confirms right turn"
    return {"format": "c412593-saved-original-sources-v1", "measurement": result,
            "original_course": course,
            "original_cameras": streams, "frames": len(frames),
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False,
            "diagnostic_fixture_only": diagnostic_fixture}


def measure_continuous_right_signal(report):
    """Return the sampled pre-turn distance and exact statutory area boundary."""
    measurement = report["measurement"]
    return {"continuous_distance_m": measurement["turn_onset"]["continuous_right_signal_distance_m"],
            "required_distance_m": measurement["required_distance_m"],
            "observed_distance_meets_boundary": measurement["observed_continuous_distance_meets_boundary"],
            "district_type": measurement["district_type"],
            "legal_judgment": "unresolved"}


def finalize_attempt(attempt, output):
    """Write derived saved outputs once; preserve every acquired source byte."""
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Use a fresh saved attempt and output")
    required = ("config.json", "route_context.json", "drive_history.jsonl",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
                *(name + ".mkv" for name in CAMERAS))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(
            "testing__C412593__NRS-484B-413-2__motor_vehicle_driver__right_") or
            config.get("cell_id") != "C412593" or
            config.get("law_id") != "NRS-484B-413-2" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != RATE_HZ or config.get("duration_s") != 45 or
            not isinstance(config.get("recording_description"), dict)):
        raise ValueError("Exact C412593 saved case configuration required")
    marker = attempt / "acquisition-provenance.json"
    provenance = json.loads(marker.read_text()) if marker.is_file() else {}
    diagnostic = provenance.get("provenance_kind") == "synthetic_fixture" and provenance.get(
        "diagnostic_fixture") is True
    report = finalize(attempt, diagnostic_fixture=diagnostic)
    observed = measure_continuous_right_signal(report)
    sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
               for name in required}
    rows = [json.loads(line) for line in (attempt / "drive_history.jsonl").read_text().splitlines()
            if line.strip()]
    channels = attempt / "channels"
    channels.mkdir()
    evidence = []
    for name in ("right_indicator", "ego_position_xy_m", "ego_heading_deg", "ego_road_id"):
        relative = "channels/" + name + ".jsonl"
        with (attempt / relative).open("x") as stream:
            for row in rows:
                if name not in row:
                    raise ValueError("Missing original recorded channel: " + name)
                stream.write(json.dumps({"original_frame": row["frame"],
                                         "time_s": row["time_s"], "value": row[name]},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": next(item["unit"] for item in
                         config["recording_description"]["channels"] if item["name"] == name),
                         "reference": relative})
    target = {"target": "continuous original right signal before sourced right turn",
              "requested": observed["required_distance_m"],
              "measured": observed["continuous_distance_m"],
              "method": "saved original-frame lamp state and sampled travel distance",
              "tolerance": 0, "matched": observed["observed_distance_meets_boundary"],
              "physical_cause_confirmed": False,
              "cause_evidence": ["drive_history.jsonl", "video_frames.jsonl", "route_context.json"]}
    result = {"case_id": case_id, "measured_values": observed,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original-source measurement; physical and legal review separate",
              "physical_failure_flags": ["Native district, sign and lamp pixels await independent review"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence, "source_evidence_hashes": sources,
              "capture_evidence_sha256": sources["capture/evidence.jsonl"],
              "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report_sources = {name: sources[name] for name in
                      ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")}
    analysis = {"format": "worker-c412593-saved-analysis",
                "case_id": case_id,
                "measurements": {"right_turn_signal_distance": {
                    "method": "measure_continuous_right_signal", "value": observed,
                    "sources": report_sources}},
                "source_report": report, "source_hashes": sources,
                "physical_checks": result["physical_checks"],
                "physical_acceptance_claimed": False,
                "legal_verdict_asserted": False}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    analysis = finalize_attempt(args.attempt, args.output)
    print(json.dumps({"case_id": analysis["case_id"],
                      "measurement_keys": list(analysis["measurements"]),
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
