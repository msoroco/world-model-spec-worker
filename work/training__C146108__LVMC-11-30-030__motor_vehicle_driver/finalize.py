"""Saved-only crosswalk pass measurement; original review remains required."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_crosswalk_pass import CAMERAS, FRAMES, HASHES, measure


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def review(path, source_kind, case_id):
    require(path.is_file(), "Missing required source: " + path.name)
    value = json.loads(path.read_text())
    require(value.get("source_kind") == source_kind and value.get("case_id") == case_id and
            value.get("reviewer") and value.get("full_interval_reviewed") is True,
            "Independent original source review missing: " + path.name)
    return value


def measure_saved(attempt, case_id):
    attempt = Path(attempt)
    sources = ("road.xodr", "crosswalk_trace.jsonl", "ego_body.jsonl", "lead_body.jsonl",
               "pedestrian_body.jsonl", "video_frames.jsonl")
    for name in sources:
        require((attempt / name).is_file(), "Missing required source: " + name)
    crossing = review(attempt / "crosswalk-review.json", "independent_original_crosswalk_review", case_id)
    purpose = review(attempt / "purpose-review.json", "independent_original_stop_purpose_review", case_id)
    require(crossing["reviewer"] != purpose["reviewer"], "Crossing and stop purpose reviewers must differ")
    require(crossing.get("native_map_sha256") == sha(attempt / "road.xodr") and
            crossing.get("crosswalk_kind") in ("marked", "unmarked_intersection") and
            crossing.get("intersection_source_id") and crossing.get("crosswalk_reference_source_id"),
            "Original crossing or intersection source missing")
    if crossing["crosswalk_kind"] == "unmarked_intersection":
        require(crossing.get("intersection_crossing_sourced") is True,
                "Unmarked intersection crossing unsourced")
    video_hashes = {name: sha(attempt / (name + ".mkv")) for name in CAMERAS}
    body_hashes = {name: sha(attempt / name) for name in
                   ("ego_body.jsonl", "lead_body.jsonl", "pedestrian_body.jsonl")}
    require(purpose.get("video_sha256") == video_hashes and
            purpose.get("body_sha256") == body_hashes and
            purpose.get("lead_stopped_for_pedestrian_sourced") is True and
            purpose.get("lead_stop_purpose_source_id") and purpose.get("pedestrian_crossing_source_id"),
            "Original stopped-lead purpose or pedestrian source missing")
    trace = rows(attempt / "crosswalk_trace.jsonl")
    frames = rows(attempt / "video_frames.jsonl")
    require(len(trace) == len(frames) == FRAMES, "600 joined original frames required")
    for i, (row, frame) in enumerate(zip(trace, frames)):
        require(row.get("video_frame") == frame.get("video_frame") == i and
                row.get("native_frame") == frame.get("native_frame") and
                row.get("source_cameras") == frame.get("source_cameras"),
                "Original Native/video frame join changed")
    source_hash = {name: sha(attempt / name) for name in sources}
    source_hash["crosswalk-review.json"] = sha(attempt / "crosswalk-review.json")
    source_hash["purpose-review.json"] = sha(attempt / "purpose-review.json")
    source_hash.update({name + ".mkv": value for name, value in video_hashes.items()})
    context = {"source_kind": "original_native_crosswalk_pass_readback",
               "crosswalk_kind": crossing["crosswalk_kind"],
               "intersection_crossing_sourced": crossing["crosswalk_kind"] == "unmarked_intersection",
               "same_direction_rear_approach": crossing.get("same_direction_rear_approach") is True,
               "lead_stopped_for_pedestrian_sourced": True,
               "crosswalk_near_x_m": crossing.get("crosswalk_near_x_m"),
               "crosswalk_far_x_m": crossing.get("crosswalk_far_x_m"),
               "lead_center_x_m": purpose.get("lead_center_x_m")}
    for name in HASHES:
        context[name + "_sha256"] = source_hash[{
            "native_map": "road.xodr", "crosswalk_reference": "crosswalk-review.json",
            "lane_directions": "road.xodr", "ego_body": "ego_body.jsonl",
            "lead_body": "lead_body.jsonl", "ego_motion": "crosswalk_trace.jsonl",
            "lead_motion": "crosswalk_trace.jsonl", "pedestrian_body_motion": "pedestrian_body.jsonl",
            "camera_manifest": "video_frames.jsonl"}[name]]
    measured = measure(context, trace)
    measured.update(case_id=case_id, source_sha256=source_hash,
                    original_crossing_reviewed=True, original_stop_purpose_reviewed=True,
                    legal_compliance="unassessed")
    return measured, trace


def measure_crosswalk(attempt, case_id):
    return measure_saved(attempt, case_id)[0]


def finalize(attempt, output):
    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    measured, observed = measure_saved(attempt, case_id)
    construction = json.loads((attempt / "construction.json").read_text())
    evidence = []
    (attempt / "channels").mkdir(exist_ok=True)
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        relative = "channels/" + name + ".jsonl"
        with (attempt / relative).open("x") as stream:
            for row in observed:
                stream.write(json.dumps({"time_s": row["time_s"], "value": row}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    instance = {item["name"]: {"source_sha256": measured["source_sha256"],
                               "original_source_review_required": True}
                for item in construction["recording_description"]["context_inputs"]}
    (attempt / "instance-context.json").write_text(json.dumps(instance, sort_keys=True) + "\n")
    for item in construction["recording_description"]["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": "instance-context.json"})
    requirements = {"crosswalk_pass_observation_" + str(i): {
        "method": "measure_crosswalk", "value": measured,
        "sources": measured["source_sha256"]} for i in range(3)}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": requirements, "source_complete": True,
              "physical_or_legal_acceptance": False}
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "source-reviewed pass at crossing",
                "requested": "source-reviewed original", "measured": measured["pass_observed"],
                "method": "measure_crosswalk", "tolerance": 0,
                "matched": measured["pass_observed"],
                "physical_cause_confirmed": False,
                "cause_evidence": list(measured["source_sha256"])}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original-source reduction; physical review pending",
              "physical_failure_flags": ["Original physical completion unconfirmed"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {}, "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
