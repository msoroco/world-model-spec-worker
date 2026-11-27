"""Saved-only original alley occupancy, dwell and goods-source reduction.

The output is measured evidence. It never decides expeditiousness or whether
an ordinance changes the rule. Missing original review is an error.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from selected_plan import plan


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite_xyz(value):
    return (isinstance(value, list) and len(value) == 3 and
            all(type(x) in (int, float) and math.isfinite(x) for x in value))


def reduce_saved(attempt, case_id):
    attempt = Path(attempt)
    survey_path = attempt / "site-survey.json"
    review_path = attempt / "goods-review.json"
    trace_path = attempt / "alley-native.jsonl"
    map_path = attempt / "video_frames.jsonl"
    for path in (survey_path, review_path, trace_path, map_path):
        require(path.is_file(), "Missing required source: " + path.name)
    survey = json.loads(survey_path.read_text())
    requested = plan(case_id, survey)
    review = json.loads(review_path.read_text())
    require(review.get("source_kind") == "independent_original_video_review"
            and review.get("case_id") == case_id
            and review.get("reviewer") not in (None, "", survey.get("reviewer"))
            and review.get("full_interval_reviewed") is True,
            "independent full-interval goods review required")
    require(review.get("video_sha256") ==
            {view: sha(attempt / (view + ".mkv")) for view in VIEWS},
            "four original video hashes missing or changed")
    require(review.get("observed_event_ids") is not None and
            isinstance(review["observed_event_ids"], list) and
            all(isinstance(item, str) and item for item in review["observed_event_ids"]),
            "observed goods event IDs missing")
    require(isinstance(review.get("observed_event_frames"), dict)
            and set(review["observed_event_frames"]) == set(review["observed_event_ids"])
            and all(type(frame) is int and 0 <= frame < 600
                    for frame in review["observed_event_frames"].values())
            and isinstance(review.get("observed_door_open_frame_ids"), list)
            and all(type(frame) is int and 0 <= frame < 600
                    for frame in review["observed_door_open_frame_ids"])
            and review.get("commercial_classification_source_id")
            and type(review.get("commercial_classification_observed")) is bool,
            "independent event and vehicle classification review required")
    trace, frames = rows(trace_path), rows(map_path)
    require(len(trace) == len(frames) == 600, "600 joined original frames required")
    require(len({row.get("vehicle_id") for row in trace}) == 1,
            "vehicle identity changed")
    stopped = []
    for index, (row, identity) in enumerate(zip(trace, frames)):
        require(row.get("source_kind") == "original_native_observation"
                and row.get("case_id") == case_id and row.get("frame") == index
                and identity.get("video_frame") == index
                and row.get("native_frame") == identity.get("native_frame")
                and abs(row.get("t_s", -100) - index / 20) < 1e-8
                and abs(identity.get("time_s", -100) - index / 20) < 1e-8,
                "original frame join changed")
        require(finite_xyz(row.get("position_xyz_m"))
                and finite_xyz(row.get("velocity_xyz_mps"))
                and row.get("alley_boundary_source_id") ==
                survey["alley_boundary_source_id"],
                "original body or alley source missing")
        speed = math.sqrt(sum(component ** 2 for component in row["velocity_xyz_mps"]))
        # A sensor rest tolerance is not a legal definition of parking.
        if speed <= .05:
            stopped.append(index)
    require(stopped, "no measured stopped interval")
    require(review.get("vehicle_within_alley_frame_ids") is not None and
            isinstance(review["vehicle_within_alley_frame_ids"], list) and
            all(type(index) is int and 0 <= index < 600
                for index in review["vehicle_within_alley_frame_ids"]),
            "reviewed alley occupancy missing")
    parked = sorted(set(stopped) & set(review["vehicle_within_alley_frame_ids"]))
    require(parked, "no independently reviewed stopped alley frames")
    event_frames = sorted(review["observed_event_frames"].values())
    last_event_frame = event_frames[-1] if event_frames else None
    stopped_after_goods = (len([frame for frame in parked if frame > last_event_frame]) / 20
                           if last_event_frame is not None else None)
    return {"format": "c378809-saved-source-measurement-v1",
            "case_id": case_id, "source_kind": "original_native_observation",
            "source_sha256": {path.name: sha(path)
                              for path in (survey_path, review_path, trace_path, map_path)},
            "frame_count": 600, "recording_duration_s": 30,
            "stopped_in_alley_frames": len(parked),
            "stopped_in_alley_duration_s": len(parked) / 20,
            "sensor_rest_tolerance_mps": .05,
            "observed_goods_event_ids": review["observed_event_ids"],
            "last_observed_goods_event_frame": last_event_frame,
            "observed_stopped_after_goods_s": stopped_after_goods,
            "requested_goods_motion": requested["goods_motion_requested"],
            "requested_idle_after_goods": requested["idle_after_goods_requested"],
            "ordinance_status_source_id": survey["ordinance_status_source_id"],
            "expeditiousness": None, "legal_result": None,
            "physical_completion": False}


def measure_alley(attempt, case_id):
    """Exact selected witness measurement from original source joins."""
    return reduce_saved(attempt, case_id)


def finalize(attempt, output):
    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    measured = measure_alley(attempt, case_id)
    sources = {name: measured["source_sha256"][name]
               for name in ("site-survey.json", "goods-review.json",
                            "alley-native.jsonl", "video_frames.jsonl")}
    channels = json.loads((attempt / "construction.json").read_text())[
        "recording_description"]["channels"]
    native = rows(attempt / "alley-native.jsonl")
    channel_evidence = []
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=True)
    review = json.loads((attempt / "goods-review.json").read_text())
    reviewed_occupancy = set(review["vehicle_within_alley_frame_ids"])
    for channel in channels:
        name = channel["name"]
        relative = "channels/" + name + ".jsonl"
        with (attempt / relative).open("x") as stream:
            for index, row in enumerate(native):
                value = (index in reviewed_occupancy if name in
                         ("st.alley", "rel.occupies") else
                         row["position_xyz_m"] if name == "kin.position" else
                         math.sqrt(sum(component ** 2 for component in
                                       row["velocity_xyz_mps"])) if name == "kin.speed" else
                         row["t_s"] if name == "kin.time" else
                         row["velocity_xyz_mps"] if name == "drv.standing_or_parked" else
                         [event_id for event_id, frame in
                          review["observed_event_frames"].items() if frame == index]
                         if name == "kin.extent" else
                         index in review["observed_door_open_frame_ids"]
                         if name == "sig.door_open" else
                         review["commercial_classification_observed"]
                         if name == "ru.commercial_motor_vehicle" else
                         json.loads((attempt / "site-survey.json").read_text())[
                             "entrance_source_id"])
                stream.write(json.dumps({"time_s": row["t_s"], "value": value}) + "\n")
        channel_evidence.append({"name": name, "unit": channel["unit"],
                                 "reference": relative})
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"alley_goods_dwell_measurement": {
                  "method": "measure_alley", "value": measured, "sources": sources}},
              "source_complete": True, "physical_or_legal_acceptance": False}
    construction = json.loads((attempt / "construction.json").read_text())
    result = {"case_id": case_id, "measured_values": measured,
              "target_checks": [{"target": "stopped in reviewed alley frames",
                  "requested": "source-reviewed stop", "measured": measured["stopped_in_alley_frames"],
                  "method": "measure_alley", "tolerance": 0,
                  "matched": measured["stopped_in_alley_frames"] > 0,
                  "physical_cause_confirmed": False,
                  "cause_evidence": list(sources)}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original-source reduction; physical review pending",
              "physical_failure_flags": ["Original physical completion unconfirmed"],
              "trace_reference": "alley-native.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": channel_evidence,
              "realized_observables": {}, "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({"case_id": report["case_id"], "source_complete": True,
                      "legal_result": None}, sort_keys=True))
