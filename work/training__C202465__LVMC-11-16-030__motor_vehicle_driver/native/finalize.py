"""Saved-only original railway sight, speed and exception measurements.

No new CARLA tick occurs here. Original acquisition bytes are read-only; each
derived measurement retains the SHA-256 of every source named in its contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rail_join import joined_row
from rail_sight import FRAME_COUNT, FRAME_RATE, FIFTEEN_MPH_MPS, measure_trace, speed_request
from source_review import load as load_review

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = (
    "road.xodr", "rail-body.jsonl", "rail-rays.jsonl",
    "reviewed-exceptions.jsonl", "reviewed-exceptions-review.json",
    "video_frames.jsonl", "trace.jsonl",
    *('original-source-review/' + role + ending for role in
      ("railway", "approach", "flagman", "signal") for ending in (".json", ".source.txt")),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _required(attempt, relative):
    path = attempt / relative
    if not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def _rows(attempt, relative):
    return [json.loads(line) for line in _required(attempt, relative).read_text().splitlines() if line]


def measure_rail_geometry(rows, measurement):
    return {"last_100_feet_sample_frames": measurement["last_100_feet_sample_frames"],
            "last_100_feet_missing_view_frames": measurement["last_100_feet_missing_view_frames"],
            "rail_vehicle_displacement_m": measurement["rail_vehicle_displacement_m"],
            "left_clear_distance_min_m": min(r["rail_left_clear_distance_m"] for r in rows),
            "right_clear_distance_min_m": min(r["rail_right_clear_distance_m"] for r in rows),
            "maximum_traversal_speed_mps": measurement["maximum_traversal_speed_mps"],
            "fifteen_mph_mps": FIFTEEN_MPH_MPS,
            "legal_visibility_conclusion": None}


def measure_exception(rows, measurement):
    return {"flagman_on_duty_frames": measurement["flagman_on_duty_frames"],
            "visible_inactive_signal_frames": measurement["visible_inactive_signal_frames"],
            "signal_indicating_frames": sum(bool(r["signal_indicates_train_approach"]) for r in rows),
            "installed_visible_signal_frames": sum(bool(r["crossing_signal_installed_visible"]) for r in rows),
            "legal_exception_conclusion": None}


def measure_selected_witness(rows, measurement):
    return {"selected_approach_frames": measurement["last_100_feet_sample_frames"],
            "crossing_traversal_frames": sum(bool(r["traversing_grade_crossing"]) for r in rows),
            "speed_source": "original body velocity_mps",
            "sight_source": "same-frame original world.cast_ray proxy",
            "legal_verdict": None}


def _review_exception_rows(attempt, frame_map, *, diagnostic_fixture):
    review = json.loads(_required(attempt, "reviewed-exceptions-review.json").read_text())
    expected = "schema_only" if diagnostic_fixture else "independently_reviewed"
    if (review.get("review_status") != expected
            or review.get("provenance_kind") != ("synthetic_fixture" if diagnostic_fixture else "original_native")
            or not review.get("reviewer_id")
            or review.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl")
            or review.get("overview_video_sha256") != sha(attempt / "overview.mkv")
            or review.get("exception_rows_sha256") != sha(attempt / "reviewed-exceptions.jsonl")):
        raise ValueError("independent per-frame exception review source differs")
    rows = _rows(attempt, "reviewed-exceptions.jsonl")
    if len(rows) != len(frame_map):
        raise ValueError("independent exception review frame count differs")
    for index, (source, mapping) in enumerate(zip(rows, frame_map)):
        if source.get("frame") != mapping.get("native_frame") or source.get("video_frame") != index:
            raise ValueError("independent exception review Native frame join failed")
        if source.get("flagman", {}).get("frame") != source["frame"] or source.get("signal", {}).get("frame") != source["frame"]:
            raise ValueError("per-frame flagman and signal observation missing")
    return rows


def finalize(attempt_dir, output_path):
    from worker_exchange.native_output import write_result

    attempt = Path(attempt_dir).resolve()
    config = json.loads(_required(attempt, "config.json").read_text())
    for relative in SOURCES:
        _required(attempt, relative)
    for camera in CAMERAS:
        _required(attempt, camera + ".mkv")
    provenance_path = attempt / "acquisition-provenance.json"
    diagnostic = provenance_path.is_file() and json.loads(provenance_path.read_text()).get("provenance_kind") == "synthetic_fixture"
    road_sha = sha(attempt / "road.xodr")
    reviews = load_review(attempt / "original-source-review", road_sha,
                          diagnostic_fixture=diagnostic)
    crossing = {"grade_crossing_source": reviews["railway"]["source_sha256"],
                "railway_source": reviews["railway"]["source_sha256"],
                "approach_route_source": reviews["approach"]["source_sha256"]}
    maps = _rows(attempt, "video_frames.jsonl")
    bodies = _rows(attempt, "rail-body.jsonl")
    rays = _rows(attempt, "rail-rays.jsonl")
    exceptions = _review_exception_rows(attempt, maps, diagnostic_fixture=diagnostic)
    trace = _rows(attempt, "trace.jsonl")
    if any(len(items) != FRAME_COUNT for items in (maps, bodies, rays, exceptions, trace)):
        raise ValueError("600 original synchronized Native frames required")
    joined = []
    for index, (mapping, body, ray, exception, motion) in enumerate(
            zip(maps, bodies, rays, exceptions, trace)):
        frame = mapping.get("native_frame")
        if (mapping.get("video_frame") != index or mapping.get("carla_frame") != frame
                or motion.get("frame") != frame
                or any(mapping.get("camera_native_frames", {}).get(name) != frame for name in CAMERAS)):
            raise ValueError("original camera, body, ray and trace frame join failed")
        row = joined_row(frame, body, ray, reviews, exception["flagman"], exception["signal"])
        row["native_frame"] = frame
        row["frame"] = index
        row["time_s"] = index / FRAME_RATE
        joined.append(row)
    measurement = measure_trace(joined, crossing)
    if min(measurement["rail_vehicle_displacement_m"].values()) < .5:
        raise ValueError("original railway traffic did not move through capture")
    source_hashes = {relative: sha(attempt / relative) for relative in SOURCES}
    context_path = attempt / "original-crossing-source-context.json"
    if context_path.exists():
        raise ValueError("retain prior crossing context; use fresh attempt")
    context_path.write_text(json.dumps({"original_crossing_source_review": {
        "source_hashes": {name: digest for name, digest in source_hashes.items()
                          if name.startswith("original-source-review/") or name == "road.xodr"},
        "review_status": "schema_only" if diagnostic else "independently_reviewed",
        "provenance_kind": "synthetic_fixture" if diagnostic else "original_native",
    }}, sort_keys=True) + "\n")
    values = {
        "rail_sight_and_speed": {"method": "measure_rail_geometry",
                                 "value": measure_rail_geometry(joined, measurement),
                                 "sources": source_hashes},
        "crossing_exceptions": {"method": "measure_exception",
                                "value": measure_exception(joined, measurement),
                                "sources": source_hashes},
        "selected_witness": {"method": "measure_selected_witness",
                             "value": measure_selected_witness(joined, measurement),
                             "sources": source_hashes},
    }
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=True)
    for name in ("st.railway_crossing", "drv.approaching", "st.sight_distance",
                 "rel.visible", "kin.speed", "ru.rail_vehicle", "dev.human_direction",
                 "dev.railway_signal_or_gate", "rel.centre_distance"):
        path = channel_dir / (name + ".jsonl")
        if path.exists():
            raise ValueError("retain prior derived channel; use fresh attempt")
        with path.open("x") as stream:
            for row in joined:
                stream.write(json.dumps({"frame": row["native_frame"],
                                         "video_frame": row["frame"],
                                         "time_s": row["time_s"],
                                         "value": row, "source": "original joined rail body/ray/review"},
                                        allow_nan=False) + "\n")
    result = {
        "case_id": config["case_id"],
        "measured_values": measurement,
        "target_checks": [{"target": "traversal_speed_mps",
                           "requested": speed_request(config["speed_mode"]),
                           "measured": measurement["maximum_traversal_speed_mps"],
                           "method": "original body velocity over crossing-line overlap",
                           "tolerance": .5, "matched": abs(measurement["maximum_traversal_speed_mps"] -
                                                          speed_request(config["speed_mode"])) <= .5,
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(source_hashes)}],
        "setup_confirmed": False,
        "behavior_attempted": True,
        "maneuver_completed": any(row["traversing_grade_crossing"] for row in joined),
        "termination_reason": "Saved original rail sight and speed measurement complete; independent physical and legal review pending",
        "physical_failure_flags": ["railway_identity_visibility_and_exception_review_pending"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": name, "unit": "structured",
                                 "reference": "channels/" + name + ".jsonl"} for name in
                                ("st.railway_crossing", "drv.approaching", "st.sight_distance",
                                 "rel.visible", "kin.speed", "ru.rail_vehicle",
                                 "dev.human_direction", "dev.railway_signal_or_gate",
                                 "rel.centre_distance")] + [{
                                     "name": "original_crossing_source_review", "unit": "structured",
                                     "reference": "original-crossing-source-context.json"}],
        "realized_observables": {
            "traversal_speed_mps": {"value": measurement["maximum_traversal_speed_mps"],
                                    "unit": "m/s", "method": "original Native body velocity",
                                    "time_window": "600 joined Native frames", "statistic": "maximum during traversal",
                                    "reference": "channels/kin.speed.jsonl"},
            "missing_view_frames": {"value": measurement["last_100_feet_missing_view_frames"],
                                    "unit": "frames", "method": "original ray proxy",
                                    "time_window": "last 100 feet of approach",
                                    "statistic": "count", "reference": "channels/st.sight_distance.jsonl"}},
        "accepted": False,
        "legal_verdict_claimed": False,
    }
    write_result(attempt, result)
    report = {"format": "lvmc-rail-saved-measurements-v1", "case_id": config["case_id"],
              "measurements": values,
              "diagnostic": {"diagnostic_fixture": diagnostic,
                             "source_sha256": source_hashes},
              "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    Path(output_path).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
