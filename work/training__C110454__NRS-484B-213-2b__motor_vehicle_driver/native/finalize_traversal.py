"""Saved-only finalization of observed two-way intersection traversal."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from finalize_base import rows, sha, verify_original_joins, video_frames


def measure_traversal(attempt):
    attempt = Path(attempt)
    source = attempt / "native_samples.jsonl"
    samples = rows(source)
    survey_path = attempt / "road_geometry.json"
    if not survey_path.is_file():
        raise ValueError("Missing required source: road_geometry.json")
    survey = json.loads(survey_path.read_text())
    directions = survey.get("road_directions_native", {})
    if set(directions) != {"approach_forward", "approach_opposing", "destination_forward", "destination_opposing"}:
        raise ValueError("Original Native two-way direction survey incomplete")
    if sum(a*b for a,b in zip(directions["approach_forward"], directions["approach_opposing"])) > -.98:
        raise ValueError("Approach lanes are not opposing two-way directions")
    polygon = survey.get("intersection_polygon_xy_m")
    if polygon != [[-7,-7],[7,-7],[7,7],[-7,7]]:
        raise ValueError("Original Native intersection polygon differs")
    moving = []
    left = []
    previous_frame = None
    previous_time = None
    for index, sample in enumerate(samples):
        frame = sample.get("native_frame")
        t = sample.get("time_s")
        if sample.get("video_frame") != index or type(frame) is not int or type(t) not in (float,int) or not math.isfinite(t):
            raise ValueError("Original video/Native frame join differs")
        if previous_frame is not None and frame != previous_frame + 1:
            raise ValueError("Original Native frame gap")
        if previous_time is not None and abs(t - previous_time - .05) > 1e-4:
            raise ValueError("Original Native timestamp gap")
        previous_frame, previous_time = frame, t
        if sample.get("two_way_native_survey") is not True:
            raise ValueError("Two-way Native survey absent")
        points = sample.get("native_body_xy_m")
        if not isinstance(points,list) or len(points) != 4 or any(
            not isinstance(p,list) or len(p) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p)
            for p in points
        ):
            raise ValueError("Original full-body footprint missing")
        speed = sample.get("speed_m_s")
        if type(speed) not in (int,float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("Original observed speed missing")
        if min(p[0] for p in points) > -7 and max(p[0] for p in points) < 7 and speed > .05:
            moving.append(index)
            if min(p[1] for p in points) > 0:
                left.append(index)
    if len(samples) != 480 or not moving:
        raise ValueError("Full moving intersection traversal absent")
    return {"value":{"moving_traversal_frames":len(moving),
                     "moving_left_traversal_frames":len(left),
                     "first_moving_frame":moving[0], "last_moving_frame":moving[-1],
                     "first_left_frame":left[0] if left else None,
                     "last_left_frame":left[-1] if left else None,
                     "legal_verdict":None},
            "method":"measure_traversal",
            "sources":{"native_samples.jsonl":sha(source),
                       "road_geometry.json":sha(survey_path)}}


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain original finalization; use a fresh attempt")
    config = json.loads((attempt / "config.json").read_text())
    if config["duration_s"] != 24 or config["rate_hz"] != 20:
        raise ValueError("Traversal requires 480 original frames")
    original = verify_original_joins(attempt,480)
    measured = measure_traversal(attempt)
    names = ("overview","approach","reference_corner","driver_reference")
    videos = [name + ".mkv" for name in names]
    video_counts = {name:video_frames(attempt / name) for name in videos}
    if any(count != 480 for count in video_counts.values()):
        raise ValueError("Original camera frame count differs")
    suffix = config["case_suffix"]
    if suffix not in ("traversal_reference","traversal_contrast"):
        raise ValueError("Unknown traversal case")
    left_frames = measured["value"]["moving_left_traversal_frames"]
    matched = left_frames == 0 if suffix == "traversal_reference" else left_frames >= 10
    endpoint = rows(attempt / "native_samples.jsonl")[-1]
    parked = math.dist(endpoint["native_center_xy_m"],[20,-5.25]) <= .8 and endpoint["speed_m_s"] <= .3
    description = config["recording_description"]
    recording_evidence = []
    for channel in description["channels"]:
        reference = "channels/" + channel["name"] + ".jsonl"
        if not (attempt / reference).is_file():
            raise ValueError("Missing required source: " + reference)
        recording_evidence.append({"name":channel["name"],"unit":channel["unit"],"reference":reference})
    for context in description["context_inputs"]:
        if not (attempt / "context.json").is_file():
            raise ValueError("Missing required source: context.json")
        recording_evidence.append({"name":context["name"],"unit":context["unit"],"reference":"context.json"})
    actual = {key:value for key,value in measured["value"].items() if key != "legal_verdict"}
    result = {"case_id":config["case_id"],"measured_values":actual,
        "target_checks":[{"target":"moving full-body left-of-center intersection traversal",
            "requested":0 if suffix == "traversal_reference" else "at_least_10",
            "measured":left_frames,"method":"saved original body, velocity and surveyed two-way intersection polygon",
            "tolerance":"50 ms sampling; physical cause and pixels require independent review",
            "matched":matched,"physical_cause_confirmed":False,
            "cause_evidence":["native_samples.jsonl","road_geometry.json"]}],
        "setup_confirmed":True,"behavior_attempted":True,"maneuver_completed":parked,
        "termination_reason":"full original duration retained",
        "physical_failure_flags":["camera_and_native_surface_review_pending"] +
            ([] if matched and parked else ["tracking_or_completion_unconfirmed"]),
        "trace_reference":"trace.jsonl","video_references":videos,
        "video_frame_map_reference":"video_frames.jsonl",
        "recording_description":description,"recording_evidence":recording_evidence,
        "realized_observables":{"moving_left_traversal_frames":{
            "value":left_frames,"unit":"frames","method":"full original body inside surveyed intersection and left of centerline while moving",
            "time_window":"original 24 s / 480 frame attempt","statistic":"count",
            "reference":"native_samples.jsonl"}},
        "provenance_kind":"native","accepted":False,"legal_verdict_claimed":False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {"format":"c110454-traversal-saved-analysis-v1",
        "case_id":config["case_id"],"candidate_id":config["candidate_id"],
        "measurements":{"intersection_traversal":measured,
            "left_side_traversal":{"value":left_frames > 0,"method":"measure_traversal",
                "sources":measured["sources"]}},
        "original_joins":original,"video_frames":video_counts,
        "scope":"saved original Native sources and decoded source videos; no independent physical acceptance or legal verdict"}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    with (attempt / "result.json").open("x") as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write("\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt",required=True)
    parser.add_argument("--output",required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))
