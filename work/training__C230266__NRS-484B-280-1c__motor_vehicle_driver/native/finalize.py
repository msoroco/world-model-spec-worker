"""Saved-only pedestrian caution measurement; never infer driver perception.

The capture trace and the separate original-source review are both required.
Diagnostic fixtures exercise this software contract but do not establish that
a human driver saw the pedestrian or that proper caution was exercised.
"""

import argparse
import hashlib
import json
from pathlib import Path

from saved_measure import reviewed_measurement


VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
          "driver_reference.mkv")
SOURCES = ("pedestrian-caution-trace.jsonl", "pedestrian-source-review.jsonl",
           "context-survey.json")


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def caution_observation(folder):
    folder = Path(folder)
    config = json.loads(required(folder, "config.json").read_text())
    first = json.loads(required(folder, SOURCES[0]).read_text().splitlines()[0])
    ego_id, pedestrian_id = first.get("ego_actor_id"), first.get("pedestrian_actor_id")
    if type(ego_id) is not int or type(pedestrian_id) is not int:
        raise ValueError("Original Native actor identities missing")
    return {"method": "caution_observation",
            "value": reviewed_measurement(
                folder, config["branch"], str(ego_id),
                str(pedestrian_id))["measurement"],
            "sources": {name: sha(required(folder, name)) for name in SOURCES}}


def analysis_report(folder):
    folder = Path(folder)
    config = json.loads(required(folder, "config.json").read_text())
    observation = caution_observation(folder)
    facts = observation["value"]
    if facts["branch"] != config["branch"] or facts["frames"] != config["frames"]:
        raise ValueError("Exact case branch or duration differs")
    return {"format": "worker-nrs280-caution-analysis-v1",
            "case_id": config["case_id"], "analysis_complete": True,
            "legal_verdict_claimed": False,
            "measurements": {"caution_observation": observation},
            "limitations": ["Visibility and a speed request do not prove actual driver observation.",
                            "Proper caution has no numeric legal threshold in the cited source.",
                            "Physical motion, statutory position and camera pixels require original-source review."]}


def derive_channels(folder):
    folder = Path(folder)
    capture = [json.loads(line) for line in required(folder, SOURCES[0]).read_text().splitlines()]
    frames = [json.loads(line) for line in required(folder, "video_frames.jsonl").read_text().splitlines()]
    if len(capture) != 600 or len(frames) != 600:
        raise ValueError("Full source/video join required")
    for index, (row, video) in enumerate(zip(capture, frames)):
        if (row.get("frame") != index or row.get("video_frame") != index or
                video.get("video_frame") != index or
                row.get("native_frame") != video.get("native_frame") or
                row.get("time_s") != video.get("time_s") or
                set(video.get("camera_native_frames", {})) !=
                {"overview", "approach", "reference_corner", "driver_reference"} or
                any(value != row["native_frame"] for value in
                    video["camera_native_frames"].values())):
            raise ValueError("Original pose, frame map and four-camera time join failed")
    channels = folder / "channels"
    channels.mkdir(exist_ok=True)
    values = {
        "native_vehicle_pedestrian_pose_and_control": [
            {"time_s": row["time_s"], "value": {
                "ego_actor_id": row["ego_actor_id"],
                "pedestrian_actor_id": row["pedestrian_actor_id"],
                "ego_xy_m": [row["ego_x_m"], row["ego_y_m"]],
                "pedestrian_xy_m": [row["ped_x_m"], row["ped_y_m"]],
                "ego_speed_mps": row["ego_speed_mps"],
                "requested_control": row["requested_control"]}} for row in capture],
        "four_camera_video": [
            {"time_s": row["time_s"], "value": row["camera_native_frames"]}
            for row in frames]}
    result = []
    for name, rows in values.items():
        path = channels / (name + ".jsonl")
        if path.exists():
            raise ValueError("Derived channel already exists: " + name)
        path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
        result.append({"name": name, "unit": "structured",
                       "reference": str(path.relative_to(folder))})
    return result


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh analysis path; retain original source")
    config = json.loads(required(attempt, "config.json").read_text())
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("Exact 600-frame capture contract changed")
    report = analysis_report(attempt)
    facts = report["measurements"]["caution_observation"]["value"]
    provenance = provenance_record(attempt)
    native = provenance["provenance_kind"] == "native" and not provenance["diagnostic_fixture"]
    result = {
        "case_id": config["case_id"], "measured_values": facts,
        "target_checks": [{
            "target": "pedestrian in the sourced statutory position and driver response after observation",
            "requested": {"mode": config["mode"], "controller": config["controller"]},
            "measured": {"position_evidenced_frames": facts["position_evidenced_frames"],
                         "line_of_sight_frames": facts["line_of_sight_frames"],
                         "first_actual_observation_frame": facts["first_actual_observation_frame"],
                         "speed_at_first_observation_mps": facts["speed_at_first_observation_mps"],
                         "speed_two_seconds_later_mps": facts["speed_two_seconds_later_mps"]},
            "method": "original Native pose/control joined to independent source review",
            "tolerance": "none; no legal proximity or caution cutoff inferred",
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": list(SOURCES)}],
        "setup_confirmed": False, "behavior_attempted": native,
        "maneuver_completed": False,
        "termination_reason": "600 captured frames require independent physical review",
        "physical_failure_flags": [
            "actual_driver_observation_unverified" if facts["actual_driver_observation_unverified"]
            else "actual_driver_observation_requires_independent_review",
            "statutory_position_and_proper_caution_require_original_source_review"],
        "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": derive_channels(attempt),
        "realized_observables": {"pedestrian_context_frames": {
            "value": facts["position_evidenced_frames"], "unit": "frames",
            "method": "separate original-source statutory-position review",
            "time_window": "600 frames", "statistic": "reviewed count",
            "reference": SOURCES[1]}},
        "provenance_kind": provenance["provenance_kind"],
        "diagnostic_fixture": provenance["diagnostic_fixture"],
        "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
