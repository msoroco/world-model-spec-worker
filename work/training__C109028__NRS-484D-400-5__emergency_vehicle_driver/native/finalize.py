"""Saved-only emergency siren analysis from retained original sources.

This emits measurements and review feedback, not legal or physical acceptance.
No requested siren or dispatch flag can substitute for independent source rows.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from source_acquisition import (read_rows, sha, validate_acoustic_capability,
                                validate_audio, validate_dispatch)

ASSIGNMENT = "training__C109028__NRS-484D-400-5__emergency_vehicle_driver"
FRAMES = 600
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
          "driver_reference.mkv")


def require(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _authorization(path, actor):
    value = json.loads(Path(path).read_text())
    if (value.get("source_kind") != "original_authorization_document" or
            value.get("vehicle_actor_id") != actor.get("actor_id") or
            value.get("vehicle_blueprint_id") != actor.get("blueprint_id") or
            not isinstance(value.get("authority_name"), str) or
            not value["authority_name"].strip() or
            not isinstance(value.get("document_identifier"), str) or
            not value["document_identifier"].strip()):
        raise ValueError("Vehicle authorization document and original actor differ")
    return {"source_sha256": sha(path), "actor_id": actor["actor_id"],
            "document_identifier": value["document_identifier"],
            "legal_authorization_verified": False}


def siren_source_measurement(attempt):
    """Case-specific measurement function for the selected requirement contract."""
    attempt = Path(attempt)
    config = json.loads(require(attempt, "config.json").read_text())
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484D-400-5" or
            config.get("cell_id") != "C109028" or
            config.get("actor") != "emergency_vehicle_driver" or
            not config.get("case_id", "").startswith(ASSIGNMENT + "__")):
        raise ValueError("Exact C109028 source identity differs")
    manifest = json.loads(require(attempt, "capture/manifest.json").read_text())
    if manifest.get("frames") != FRAMES or manifest.get("extraction_confirmed") is not True:
        raise ValueError("Complete original 600-frame extraction absent")
    native = read_rows(require(attempt, "native_samples.jsonl"))
    mapping = read_rows(require(attempt, "video_frames.jsonl"))
    trace = read_rows(require(attempt, "trace.jsonl"))
    evidence = read_rows(require(attempt, "capture/evidence.jsonl"))
    if any(len(group) != FRAMES for group in (native, mapping, trace, evidence)):
        raise ValueError("Full original Native/trace/evidence frame window required")
    first_time = mapping[0].get("time_s")
    if type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError("Original frame time absent")
    previous = None
    positions, lamp_state = [], []
    for index, (sample, frame, scene, facts) in enumerate(zip(
            native, mapping, trace, evidence)):
        native_frame = frame.get("carla_frame")
        if (type(native_frame) is not int or
                (previous is not None and native_frame <= previous) or
                frame.get("native_frame") != native_frame or
                frame.get("video_frame") != index or
                sample.get("native_frame") != native_frame or
                scene.get("frame") != native_frame or
                facts.get("original_frame") != native_frame):
            raise ValueError("Original Native/video/trace/evidence frame join differs")
        previous = native_frame
        expected = first_time + index / 20
        if any(type(t) not in (int, float) or not math.isfinite(t) or
               abs(t - expected) > .003 for t in
               (frame.get("time_s"), sample.get("time_s"),
                scene.get("time_s"))):
            raise ValueError("Original Native/video/trace time join differs")
        ego = sample.get("ego", {})
        other = sample.get("other", {})
        center = ego.get("center_xy_m")
        if (sample.get("source_kind") != "original_native" or
                not isinstance(center, list) or len(center) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x)
                    for x in center) or
                len(ego.get("body_vertices_m", [])) < 8 or
                len(other.get("body_vertices_m", [])) < 8 or
                type(sample.get("special1_native_readback")) is not bool):
            raise ValueError("Original emergency actor/body/lamp readback incomplete")
        if any(abs(a-b) > .01 for a, b in zip(
                center, scene.get("position_m", [])[:2])):
            raise ValueError("Original Native ego pose differs from trace")
        positions.append(center)
        lamp_state.append(sample["special1_native_readback"])
    audio = validate_audio(require(attempt, "microphone-pcm16.json"),
                           require(attempt, "audio_observations.jsonl"),
                           require(attempt, "video_frames.jsonl"))
    dispatch = validate_dispatch(require(attempt, "dispatch.jsonl"),
                                 require(attempt, "video_frames.jsonl"),
                                 require(attempt, "dispatch-source.json"))
    authorization = _authorization(require(attempt, "vehicle-authorization.json"),
                                   native[0]["ego"])
    acoustic = validate_acoustic_capability(
        require(attempt, "acoustic-report.json"),
        require(attempt, "microphone-pcm16.json"))
    drows = read_rows(attempt / "dispatch.jsonl")
    sounding = audio["siren_audible_by_frame"]
    response = [row["emergency_call_documented"] or
                row["immediate_pursuit_documented"] for row in drows]
    outside = sum(sound and not qualifying for sound, qualifying in
                  zip(sounding, response))
    approach = [position[0] < config["intersection_x_m"]
                for position in positions]
    progress = math.dist(positions[0], positions[-1])
    if progress < 1:
        raise ValueError("Original emergency vehicle did not progress")
    return {"frames": FRAMES,
            "observed_siren_frames": sum(sounding),
            "observed_warning_lamp_frames": sum(lamp_state),
            "documented_emergency_call_frames": dispatch["emergency_call_frames"],
            "documented_immediate_pursuit_frames": dispatch["immediate_pursuit_frames"],
            "siren_outside_documented_response_frames": outside,
            "siren_during_approach_frames": sum(s and a for s, a in
                                                 zip(sounding, approach)),
            "original_motion_progress_m": progress,
            "acoustic_source_assessment": acoustic["source_assessment"],
            "acoustic_assessment_distance_ft": acoustic["distance_ft"],
            "authorization_document_identifier": authorization["document_identifier"],
            "legal_authorization_verified": False,
            "legal_equipment_conclusion": None,
            "legal_siren_use_conclusion": None,
            "sources": {name: sha(require(attempt, name)) for name in (
                "native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
                "capture/evidence.jsonl", "microphone-pcm16.json",
                "audio_observations.jsonl", "dispatch.jsonl",
                "dispatch-source.json", "vehicle-authorization.json",
                "acoustic-report.json")}}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh saved analysis directory")
    value = siren_source_measurement(attempt)
    config = json.loads(require(attempt, "config.json").read_text())
    for video in VIDEOS:
        require(attempt, video)
    target = ("observed_siren_during_documented_response" if
              config.get("siren_requested") else "observed_lamps_without_siren")
    if config.get("siren_requested"):
        matched = (value["observed_siren_frames"] > 0 and
                   (value["siren_outside_documented_response_frames"] == 0) ==
                   bool(config.get("emergency_call_requested") or
                        config.get("immediate_pursuit_requested")))
    else:
        matched = (value["observed_siren_frames"] == 0 and
                   value["observed_warning_lamp_frames"] > 0)
    result = {"case_id": config["case_id"],
              "measured_values": {"siren_source": value},
              "target_checks": [{"target": target, "requested": True,
                                 "measured": matched,
                                 "method": "independent microphone, dispatch and Native frame join",
                                 "tolerance": 0, "matched": matched,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(value["sources"])}],
              "setup_confirmed": True,
              "behavior_attempted": True,
              "maneuver_completed": True,
              "termination_reason": "full saved 30-second source window",
              "trace_reference": "trace.jsonl",
              "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [
                  {"name": channel["name"], "unit": channel["unit"],
                   "reference": "observables/" + channel["name"] + ".jsonl"}
                  for channel in config["recording_description"]["channels"]] +
                  [{"name": "dispatch_authorization", "unit": "structured",
                    "reference": "source_context.json"}],
              "physical_failure_flags": [
                  "500ft_acoustic_and_authorization_require_independent_review",
                  "actual_pixels_and_other_driver_warning_unreviewed"],
              "realized_observables": {"siren_source": value},
              "provenance_kind": "native",
              "accepted": False, "legal_verdict_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result
    audio_rows = read_rows(attempt / "audio_observations.jsonl")
    dispatch_rows = read_rows(attempt / "dispatch.jsonl")
    native_rows = read_rows(attempt / "native_samples.jsonl")
    capture_rows = read_rows(attempt / "capture/evidence.jsonl")
    acoustic_report = json.loads(require(attempt, "acoustic-report.json").read_text())
    channel_names = {row["name"] for row in config["recording_description"]["channels"]}
    required_channels = {"ru.emergency_vehicle", "sig.siren", "sig.warning_lamp",
                         "drv.responding_emergency", "kin.velocity", "ru.pedestrian",
                         "ru.motor_vehicle", "drv.approaching",
                         "observer_distance_ft", "other_approach_distance_m"}
    if not required_channels <= channel_names:
        raise ValueError("Mandatory original source channels absent")
    observed = attempt / "observables"
    observed.mkdir()
    streams = {name: (observed / (name + ".jsonl")).open("x")
               for name in channel_names}
    try:
        for index, (audio_row, dispatch_row, native_row, capture_row) in enumerate(
                zip(audio_rows, dispatch_rows, native_rows, capture_rows)):
            ego, other = native_row["ego"], native_row["other"]
            other_body = other["body_vertices_m"]
            other_center = [sum(vertex[axis] for vertex in other_body) / len(other_body)
                            for axis in (0, 1)]
            values = {
                "ru.emergency_vehicle": {"actor_id": ego["actor_id"],
                    "blueprint_id": ego["blueprint_id"],
                    "authorization_document_identifier": value["authorization_document_identifier"]},
                "sig.siren": {"audible": audio_row["siren_audible"],
                              "microphone_source_sha256": value["sources"]["microphone-pcm16.json"]},
                "sig.warning_lamp": {"special1_native_readback": native_row["special1_native_readback"]},
                "drv.responding_emergency": {
                    "emergency_call_documented": dispatch_row["emergency_call_documented"],
                    "immediate_pursuit_documented": dispatch_row["immediate_pursuit_documented"]},
                "kin.velocity": {"speed_mps": ego.get("speed_mps"),
                                  "center_xy_m": ego["center_xy_m"]},
                "ru.pedestrian": {"observed_count": sum(
                    str(actor.get("blueprint", "")).startswith("walker.")
                    for actor in capture_row.get("original_observations", {}).get("participants", []))},
                "ru.motor_vehicle": {"actor_id": other.get("actor_id"),
                                     "blueprint_id": other.get("blueprint_id"),
                                     "body_vertices_m": other["body_vertices_m"]},
                "drv.approaching": {"before_intersection":
                    ego["center_xy_m"][0] < config["intersection_x_m"],
                    "intersection_x_m": config["intersection_x_m"]},
                "observer_distance_ft": acoustic_report["distance_ft"],
                "other_approach_distance_m": math.dist(
                    other_center, [config["intersection_x_m"], 0.0]),
            }
            if "siren_source" in channel_names:
                values["siren_source"] = {"audible": audio_row["siren_audible"]}
            for name, stream in streams.items():
                stream.write(json.dumps({"time_s": native_row["time_s"],
                                         "value": values[name]}, allow_nan=False) + "\n")
    finally:
        for stream in streams.values():
            stream.close()
    (attempt / "source_context.json").write_text(json.dumps({
        "dispatch_authorization": {
            "authorization_document_identifier": value["authorization_document_identifier"],
            "documented_emergency_call_frames": value["documented_emergency_call_frames"],
            "documented_immediate_pursuit_frames": value["documented_immediate_pursuit_frames"],
            "legal_authorization_verified": False}}, indent=2) + "\n")
    result = physical_result(attempt, result)
    validate_result(result)
    report = {"format": "c109028-saved-source-analysis-v1",
              "case_id": config["case_id"],
              "measurements": {"siren_source_measurement": {
                  "method": "siren_source_measurement", "value": value,
                  "sources": value["sources"]}},
              "original_source_hashes": value["sources"],
              "legal_or_physical_acceptance": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    with (attempt / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
