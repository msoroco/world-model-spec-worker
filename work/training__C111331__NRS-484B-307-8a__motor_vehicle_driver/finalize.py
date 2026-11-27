"""Saved-only source measurements for C111331 steady red, with no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from red_observations import analyze


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_FILES = ("steady-red-native-samples.jsonl", "signal_survey.json",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return path


def rows(path):
    return [json.loads(line) for line in source(path).read_text().splitlines() if line.strip()]


def decoded_frames(path):
    source(path)
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                           capture_output=True, text=True, timeout=120)
    if probe.returncode or not probe.stdout.strip().isdigit():
        raise ValueError("Four-camera source decode failed: " + path.name)
    return int(probe.stdout.strip())


def measure_activation(attempt, config, observed):
    return {"value": observed["signal_governing_id"],
            "method": "measure_activation",
            "sources": {name: sha(source(attempt / name)) for name in
                        ("steady-red-native-samples.jsonl", "signal_survey.json", "video_frames.jsonl")},
            "physical_and_legal_outcome_unverified": True}


def measure_stop_and_hold(attempt, config, observed):
    samples = rows(attempt / "steady-red-native-samples.jsonl")
    count = sum(row["signal_state"] == "red" and row["ego_speed_mps"] == 0 and
                row["ego_front_y_m"] < observed["stop_reference_y_m"] for row in samples)
    return {"value": count, "method": "measure_stop_and_hold",
            "sources": {name: sha(source(attempt / name)) for name in SOURCE_FILES},
            "diagnostics": observed, "physical_and_legal_outcome_unverified": True}


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved attempt and preserve original acquisition")
    config = json.loads(source(attempt / "config.json").read_text())
    if config.get("duration_s") != 24 or config.get("rate_hz") != 20 or config.get("frames") != 480:
        raise ValueError("Exact 480-frame source window changed")
    survey = json.loads(source(attempt / "signal_survey.json").read_text())
    fixture = survey.get("source_kind") == "synthetic_native_sample"
    if not fixture and survey.get("source_kind") != "original_native_signal_survey":
        raise ValueError("Missing original Native survey provenance")
    samples = rows(attempt / "steady-red-native-samples.jsonl")
    frame_map = rows(attempt / "video_frames.jsonl")
    native_trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    if any(len(x) != 480 for x in (samples, frame_map, native_trace, evidence)):
        raise ValueError("Incomplete original Native frame/source join")
    for i, (sample, frame, trace, packet) in enumerate(zip(samples, frame_map, native_trace, evidence)):
        native = frame.get("native_frame")
        if sample.get("frame") != i or sample.get("native_frame") != native or \
                trace.get("frame") != native or packet.get("original_frame") != native or \
                frame.get("video_frame") != i or abs(sample.get("time_s", -1) - frame.get("time_s", -2)) > .001:
            raise ValueError("Original Native and video frame join differs")
    observed = analyze(samples, expected_signal_id=survey["governing_signal_id"], allow_fixture=fixture)
    videos = {name + ".mkv": decoded_frames(attempt / (name + ".mkv")) for name in VIEWS}
    if any(count != 480 for count in videos.values()):
        raise ValueError("Four-camera 480-frame source incomplete")
    description = config["recording_description"]
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=False)
    channels = {}
    for spec in description["channels"]:
        name = spec["name"]
        values = []
        for row in samples:
            value = {
                "dev.traffic_signal": row["signal_state"],
                "dev.governs": row["governing_signal_id"],
                "st.lane_enters": row["intersection_entry_y_m"],
                "st.crosswalk": {"present": row["nearest_crosswalk_y_m"] is not None,
                                 "y_m": row["nearest_crosswalk_y_m"]},
                "dev.regulatory_sign": {"present": row["indicated_sign_y_m"] is not None,
                                         "y_m": row["indicated_sign_y_m"]},
                "st.stop_line": {"present": row["indicated_marking_y_m"] is not None,
                                 "y_m": row["indicated_marking_y_m"]},
                "st.intersection": row["intersection_entry_y_m"],
                "drv.stopped": row["ego_speed_mps"] == 0,
                "drv.crossing_line": row["ego_front_y_m"] >= observed["stop_reference_y_m"],
                "drv.entering_intersection": row["ego_front_y_m"] >= row["intersection_entry_y_m"],
                "kin.velocity": row["ego_speed_mps"],
                "drv.extreme_lane": row["ego_lane_extreme"],
                "st.one_way_roadway": row["downstream_direction"],
                "drv.yields_to": {"pedestrian": row["pedestrian_yielded"],
                                  "traffic": row["traffic_yielded"]},
            }[name]
            values.append({"time_s": row["time_s"], "value": value})
        destination = channel_dir / (name + ".jsonl")
        destination.write_text("".join(json.dumps(x, separators=(",", ":")) + "\n" for x in values))
        channels[name] = destination
    refs = [{"name": spec["name"], "unit": spec["unit"],
             "reference": "channels/" + spec["name"] + ".jsonl"} for spec in description["channels"]]
    (channel_dir / "signal_survey.json").write_text(json.dumps({"signal_survey": survey}) + "\n")
    refs.append({"name": "signal_survey", "unit": "structured",
                 "reference": "channels/signal_survey.json"})
    result = {
        "case_id": config["case_id"],
        "measured_values": {"first_full_stop_frame": observed["first_full_stop_frame"],
                            "first_reference_crossing_frame": observed["first_reference_crossing_frame"],
                            "first_green_frame": observed["first_green_frame"],
                            "red_departure_frame": observed["red_departure_frame"]},
        "target_checks": [{"target": "source-observed steady-red stopped-frame count",
                           "requested": config["controller"],
                           "measured": measure_stop_and_hold(attempt, config, observed),
                           "method": "original Native body/signal/frame join",
                           "tolerance": None, "matched": None,
                           "physical_cause_confirmed": False,
                           "cause_evidence": [sha(attempt / name) for name in SOURCE_FILES]}],
        "setup_confirmed": False, "behavior_attempted": not fixture,
        "maneuver_completed": False,
        "termination_reason": "full saved 480-frame steady-red trace analyzed",
        "physical_failure_flags": ["signal_facing_and_original_pixels_review_required"] +
                                  (["synthetic_fixture_not_physical"] if fixture else []),
        "trace_reference": "trace.jsonl", "video_references": list(videos),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": refs,
        "realized_observables": {}, "physical_checks": {"steady_red_diagnostics": observed},
        "provenance_kind": "synthetic_cpu_fixture" if fixture else "native",
        "accepted": False, "legal_verdict_claimed": False,
    }
    from worker_exchange.native_output import physical_result, validate_result, write_result
    result = physical_result(attempt, result)
    result["physical_observations"]["steady_red_diagnostics"] = observed
    validate_result(result)
    report = {"format": "worker-c111331-steady-red-saved-analysis-v1",
              "case_id": config["case_id"],
              "measurements": {"signal_governing_id": measure_activation(attempt, config, observed),
                               "red_stopped_frames": measure_stop_and_hold(attempt, config, observed)},
              "source_hashes": {name: sha(attempt / name) for name in SOURCE_FILES},
              "four_camera_frames": videos,
              "actual_pixels_review_required": True,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    write_result(attempt, result)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(finalize(arguments.attempt, arguments.output), sort_keys=True))
