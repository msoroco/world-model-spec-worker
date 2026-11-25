"""Convert original C111071 Native readback to saved measurement inputs.

The review must bind the original readback and imported device survey. A
synthetic CPU review exercises this code but cannot establish physical facts.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from cycle_controller import EGO_FACE, FRAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def convert(attempt: Path, review_path: Path):
    attempt = Path(attempt)
    raw_path = attempt / "native_raw_readback.jsonl"
    frames_path = attempt / "video_frames.jsonl"
    survey_path = attempt / "map-import-survey.json"
    for path in (raw_path, frames_path, survey_path, review_path):
        require(path.is_file(), "Missing original source or bound review: " + path.name)
    review = json.loads(review_path.read_text())
    survey = json.loads(survey_path.read_text())
    source_hashes = {path.name: sha(path) for path in (raw_path, frames_path, survey_path)}
    require(review.get("source_sha256") == source_hashes,
            "Review does not bind the original Native sources")
    require(review.get("review_kind") == "original_source_review" and
            isinstance(review.get("reviewer"), str) and review["reviewer"].strip(),
            "Named original source review absent")
    require(review.get("governing_face") == EGO_FACE and
            review.get("governing_face_source_refs"),
            "Reviewed governing signal face absent")
    require(review.get("other_device_prohibition_survey") is False and
            review.get("other_device_source_refs"),
            "Reviewed other-device prohibition survey absent")
    require(review.get("detector_request_observed") is True and
            review.get("detector_request_source_refs") and
            review.get("detector_serviced_before_entry") is False,
            "Reviewed detector request and service history absent")
    require(review.get("participant_lawful_status_source_refs"),
            "Reviewed participant lawful status source absent")
    reference = survey.get("road_reference", {})
    required_reference = ("map_sha256", "stop_marking_y_m", "nearest_crosswalk_y_m",
                          "junction_entry_y_m", "approach_road_id", "lane_id",
                          "detector_center_x_m", "detector_y_m",
                          "detector_half_width_m", "detector_half_length_m")
    require(all(key in reference for key in required_reference),
            "Original source road reference absent")
    require(reference["map_sha256"] == survey.get("map_sha256"),
            "Original source road hash differs")
    require(reference["stop_marking_y_m"] < reference["nearest_crosswalk_y_m"] <
            reference["junction_entry_y_m"], "Original stop hierarchy geometry differs")
    heads = {row["role"]: row for row in survey.get("signal_actors", [])}
    require(set(heads) == {"red", "arrow", "cross"} and
            len({row["id"] for row in heads.values()}) == 3,
            "Original imported governing signal survey absent")
    raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line]
    frames = [json.loads(line) for line in frames_path.read_text().splitlines() if line]
    require(len(raw) == len(frames) == FRAMES, "Original 600-frame Native join absent")
    require(review.get("lawful_conflict_by_frame") is not None and
            len(review["lawful_conflict_by_frame"]) == FRAMES,
            "Reviewed lawful conflict frame coverage absent")
    rows = []
    prior_frame = -1
    prior_time = -math.inf
    cycles = 0
    prior_phase = None
    for index, (source, mapped, lawful) in enumerate(zip(raw, frames,
                                                         review["lawful_conflict_by_frame"])):
        frame, time = source.get("native_frame"), source.get("time_s")
        require(type(frame) is int and frame > prior_frame and
                type(time) in (int, float) and math.isfinite(time) and time > prior_time and
                mapped.get("native_frame") == frame and mapped.get("video_frame") == index and
                abs(mapped.get("time_s", -math.inf) - time) <= 1e-4,
                "Original Native/video frame or time join differs")
        require(source.get("source_kind") == "native_observation" and
                source.get("road_relation_from_original_body", {}).get("source_map_sha256") == reference["map_sha256"],
                "Original body and source road relation absent")
        require(source.get("signal_actor_ids") == {role: row["id"] for role, row in heads.items()},
                "Original signal actor identity differs")
        signal = source.get("signal_readback", {})
        require(signal.get("red") == "red" and signal.get("arrow") == "green" and
                signal.get("cross") in ("green", "yellow", "red"),
                "Original steady signal readback differs")
        phase = "cross_" + signal["cross"]
        if prior_phase == "cross_red" and phase == "cross_green":
            cycles += 1
        require(source.get("controller_cycle_count_from_readback") == cycles,
                "Original controller cycle count differs from signal readback")
        require(type(lawful) is dict and type(lawful.get("pedestrians_in_crosswalk")) is bool and
                type(lawful.get("lawful_traffic_conflict")) is bool and lawful.get("source_refs"),
                "Reviewed lawful conflict frame absent")
        relation = source["road_relation_from_original_body"]
        require(type(relation.get("entered_intersection_by_body")) is bool and
                type(relation.get("detector_footprint_intersects_ego_body")) is bool,
                "Original body road relation incomplete")
        require(type(source.get("speed_mps")) in (int, float) and
                math.isfinite(source["speed_mps"]) and source["speed_mps"] >= 0 and
                isinstance(source.get("body_vertices_m"), list) and
                len(source["body_vertices_m"]) == 8,
                "Original ego body or speed absent")
        body = source["body_vertices_m"]
        require(all(isinstance(vertex, list) and len(vertex) == 3 and
                    all(type(value) in (int, float) and math.isfinite(value)
                        for value in vertex) for vertex in body),
                "Original ego body vertices invalid")
        xs, ys = [vertex[0] for vertex in body], [vertex[1] for vertex in body]
        front = max(ys)
        detector_overlap = (max(xs) >= reference["detector_center_x_m"] - reference["detector_half_width_m"] and
                            min(xs) <= reference["detector_center_x_m"] + reference["detector_half_width_m"] and
                            max(ys) >= reference["detector_y_m"] - reference["detector_half_length_m"] and
                            min(ys) <= reference["detector_y_m"] + reference["detector_half_length_m"])
        require(relation["entered_intersection_by_body"] ==
                (front >= reference["junction_entry_y_m"]) and
                relation["detector_footprint_intersects_ego_body"] == detector_overlap and
                abs(relation.get("front_to_stop_marking_m", math.inf) -
                    (reference["stop_marking_y_m"] - front)) <= 1e-6 and
                abs(relation.get("front_to_crosswalk_m", math.inf) -
                    (reference["nearest_crosswalk_y_m"] - front)) <= 1e-6,
                "Original body road relation differs from retained vertices and map")
        rows.append({"native_frame": frame, "time_s": time,
                     "signal_actor_id": heads["red"]["id"],
                     "cross_signal_actor_id": heads["cross"]["id"],
                     "ego_face_observed": EGO_FACE,
                     "cross_phase_observed": phase,
                     "controller_cycle_count": cycles,
                     "actor_class_observed": "motorcycle",
                     "detector_request_present": True,
                     "detector_request_serviced": False,
                     "other_device_prohibition_observed": False,
                     "body_vertices_m": source["body_vertices_m"],
                     "speed_mps": source["speed_mps"],
                     "speed_provenance": "original_native_readback_and_bound_review",
                     "entered_intersection": relation["entered_intersection_by_body"],
                     "pedestrians_in_crosswalk": lawful["pedestrians_in_crosswalk"],
                     "lawful_traffic_conflict": lawful["lawful_traffic_conflict"]})
        prior_frame, prior_time, prior_phase = frame, time, phase
    require(not (attempt / "native_samples.jsonl").exists() and
            not (attempt / "road_geometry.json").exists() and
            not (attempt / "source-review.json").exists(),
            "Derived measurement source already exists")
    geometry = {"signal_actor_id": heads["red"]["id"],
                "cross_signal_actor_id": heads["cross"]["id"],
                "governing_face": EGO_FACE, "approach_enters_intersection": True,
                "stop_reference_kind": "stop_sign_or_marking",
                "approach_axis": 1, "approach_sign": 1,
                "stop_reference_coordinate_m": reference["stop_marking_y_m"],
                "other_device_prohibition_survey": False,
                "original_source_sha256": source_hashes,
                "review_sha256": sha(review_path),
                "physical_detector_causation_verified": False}
    (attempt / "native_samples.jsonl").write_text("".join(
        json.dumps(row, allow_nan=False) + "\n" for row in rows))
    (attempt / "road_geometry.json").write_text(
        json.dumps(geometry, indent=2, allow_nan=False) + "\n")
    (attempt / "source-review.json").write_bytes(review_path.read_bytes())
    return {"frames": FRAMES, "source_sha256": source_hashes,
            "review_sha256": sha(review_path), "physical_detector_causation_verified": False}
