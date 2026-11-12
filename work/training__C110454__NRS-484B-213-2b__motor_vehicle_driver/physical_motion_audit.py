"""Independent original-frame physical-motion check for selected C110454 cases.

Diagnostic mode exercises source-shaped geometry but can never verify Native motion.
Statutory geometry is measured here; legal applicability and pixels need separate review.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from source_join_audit import audit as audit_sources, read, require, rows, sha

HERE = Path(__file__).resolve().parent
EXPECTED = {"rail_reference": "outside_100_ft", "rail_contrast": "within_100_ft",
            "rail_at": "within_100_ft",
            "oneway_absent": "within_100_ft", "oneway_present": "within_100_ft",
            "traversal_reference": "no_left_traversal", "traversal_contrast": "left_traversal"}


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def point(value):
    return isinstance(value, list) and len(value) == 2 and all(number(v) for v in value)


def measure_rows(samples: list[dict], survey: dict, suffix: str, context: dict | None = None,
                 *, enforce_target: bool = True) -> dict:
    require(suffix in EXPECTED and len(samples) == 480, "Selected 480-frame motion interval required")
    directions = survey.get("road_directions_native", {})
    require(set(directions) == {"approach_forward", "approach_opposing",
                                "destination_forward", "destination_opposing"} and
            all(point(value) for value in directions.values()),
            "Native road-direction survey incomplete")
    one_way = suffix == "oneway_present"
    require(survey.get("one_way_native_readback") is one_way if not suffix.startswith("traversal_") else
            sum(a*b for a, b in zip(directions["approach_forward"],
                                    directions["approach_opposing"])) < -.98,
            "Native roadway designation differs")
    if suffix.startswith("rail_"):
        require(survey.get("railroad_crossing_native_readback") is True and
                isinstance(survey.get("railroad_crossing_object_id"), str) and
                bool(survey["railroad_crossing_object_id"]),
                "Native railroad object readback missing")
    if suffix.startswith("traversal_"):
        require(survey.get("intersection_polygon_xy_m") == [[-7, -7], [7, -7], [7, 7], [-7, 7]],
                "Native intersection polygon differs")
        require(context is not None and
                context.get("surveyed_two_way_intersection") == survey,
                "Native traversal context differs")
    else:
        require(context is not None and context.get("case_suffix") == suffix and
                context.get("zone_kind") == survey.get("approach_zone_kind") and
                context.get("one_way") is one_way and
                context.get("railroad_crossing") is suffix.startswith("rail_") and
                context.get("boundary_x_m") == survey.get("approach_boundary_x_m") and
                context.get("railroad_crossing_object_id") == survey.get("railroad_crossing_object_id") and
                context.get("original_frames") == [row.get("native_frame") for row in samples],
                "Native statutory context differs")
    left_approach, moving_traversal, moving_left = [], [], []
    previous_frame, previous_time = None, None
    for index, row in enumerate(samples):
        frame, time = row.get("native_frame"), row.get("time_s")
        require(type(frame) is int and number(time) and row.get("video_frame") == index and
                (previous_frame is None or frame == previous_frame + 1) and
                (previous_time is None or abs(time - previous_time - .05) <= 1e-4),
                "Original motion frame/time gap")
        previous_frame, previous_time = frame, time
        body = row.get("native_body_xy_m")
        require(isinstance(body, list) and len(body) == 4 and all(point(p) for p in body) and
                row.get("body_xy_m") == body and point(row.get("native_center_xy_m")),
                "Original full-body motion sample differs")
        speed = row.get("speed_m_s")
        require(number(speed) and speed >= 0 and
                row.get("two_way_native_survey") is (not one_way),
                "Original Native speed or direction sample differs")
        if not suffix.startswith("traversal_"):
            require(row.get("one_way_native_survey") is one_way,
                    "Native one-way sample differs")
            boundary = survey["approach_boundary_x_m"]
            require(number(boundary), "Native zone boundary missing")
            if min(p[1] for p in body) > 0 and max(p[0] for p in body) < boundary and speed > .05:
                left_approach.append(boundary - max(p[0] for p in body))
        elif min(p[0] for p in body) > -7 and max(p[0] for p in body) < 7 and speed > .05:
            moving_traversal.append(index)
            if min(p[1] for p in body) > 0:
                moving_left.append(index)
    endpoint = samples[-1]
    parked = math.dist(endpoint["native_center_xy_m"], [20, -5.25]) <= .8 and endpoint["speed_m_s"] <= .3
    if enforce_target:
        require(parked, "Native endpoint parking not observed")
    if suffix.startswith("traversal_"):
        require(bool(moving_traversal), "Moving full-body traversal absent")
        relation = "left_traversal" if moving_left else "no_left_traversal"
        measured = {"moving_traversal_frames": len(moving_traversal),
                    "moving_left_traversal_frames": len(moving_left)}
    else:
        require(bool(left_approach), "Driven full-body left-side interval absent")
        nearest = min(left_approach)
        relation = "within_100_ft" if nearest <= 30.48 + 1e-6 else "outside_100_ft"
        measured = {"left_driving_frames": len(left_approach),
                    "nearest_body_front_to_zone_m": nearest,
                    "100_ft_boundary_m": 30.48,
                    "zone_kind": survey["approach_zone_kind"],
                    "one_way_native_survey": one_way}
    if enforce_target:
        require(relation == EXPECTED[suffix], "Native motion differs from selected case")
    return {"observed_relation": relation, "measured": measured,
            "endpoint_parked": parked, "original_frames": 480}


def audit(attempt: Path, processing: Path, case_id: str, candidate_id: str,
          construction_sha256: str, *, diagnostic: bool = False) -> dict:
    attempt, processing = Path(attempt).resolve(), Path(processing).resolve()
    prefix = HERE.name + "__"
    require(case_id.startswith(prefix), "Wrong C110454 case")
    suffix = case_id.removeprefix(prefix)
    require(suffix in EXPECTED, "Unselected case motion audit")
    joined = audit_sources(attempt, processing, case_id, candidate_id,
                           construction_sha256, diagnostic=diagnostic)
    survey_path = attempt / "road_geometry.json"
    context_path = attempt / ("context.json" if suffix.startswith("traversal_") else
                              "statutory_context.json")
    require(survey_path.is_file() and context_path.is_file(), "Native road or context source missing")
    saved = read(processing)
    require(saved.get("original_source_hashes", {}).get(survey_path.name) == sha(survey_path) and
            saved.get("original_source_hashes", {}).get(context_path.name) == sha(context_path),
            "Saved Native road/context source differs")
    measured = measure_rows(rows(attempt / "native_samples.jsonl"), read(survey_path),
                            suffix, read(context_path))
    return {"format": "c110454-physical-motion-cpu-v1", "case_id": case_id,
            "candidate_id": candidate_id,
            "source_sha256": {"native_samples.jsonl": sha(attempt / "native_samples.jsonl"),
                              survey_path.name: sha(survey_path), context_path.name: sha(context_path)},
            "saved_processing_sha256": joined["saved_processing_sha256"],
            "diagnostic_fixture": diagnostic,
            "source_shaped_motion_status": "matched",
            "native_motion_status": "unverified" if diagnostic else "met",
            "physical_motion_verified": not diagnostic,
            "physical_completion_verified": False,
            "legal_verdict_claimed": False, **measured}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--construction-sha256", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.case, args.candidate,
                           args.construction_sha256, diagnostic=args.diagnostic), indent=2))
