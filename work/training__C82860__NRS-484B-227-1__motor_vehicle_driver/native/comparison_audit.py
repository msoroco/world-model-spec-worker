"""Audit the fixed context of two saved divided-road U-turn measurements."""

import json
from pathlib import Path

from measure_uturn import measure_attempt
from road_request import CAMERAS, request


def audit(opening_attempt, barrier_attempt):
    attempts = (Path(opening_attempt), Path(barrier_attempt))
    suffixes = ("authorized_opening", "barrier_crossing")
    contexts = []
    measurements = []
    fixed_configs = []
    for path, suffix in zip(attempts, suffixes):
        actual_request = json.loads((path / "request.json").read_text())
        if actual_request != request(suffix):
            raise ValueError("Exact comparison request or controlled location differs")
        config = json.loads((path / "config.json").read_text())
        if config.get("selected_case_id") != actual_request["case_id"]:
            raise ValueError("Exact comparison selected case differs")
        fixed_configs.append({key: config.get(key) for key in
                              ("cell_id", "law_id", "actor", "rate_hz", "duration_s",
                               "frames", "cameras", "physical_completion")})
        context = json.loads((path / "divided-road-context.json").read_text())
        review = json.loads((path / "source-review.json").read_text())
        contexts.append((context, review))
        measurements.append(measure_attempt(path))
    left, right = contexts
    if fixed_configs[0] != fixed_configs[1]:
        raise ValueError("Fixed camera, duration or physical criterion differs")
    for key in ("authored_road_ids", "median_bounds_m", "opening_bounds_m",
                "barrier_bounds_m", "source_kind", "native_roadways"):
        if left[0].get(key) != right[0].get(key):
            raise ValueError("Fixed original road or median context differs: " + key)
    if left[1]["source"]["sha256"] != right[1]["source"]["sha256"]:
        raise ValueError("Fixed authority source differs")
    opening, barrier = measurements
    if opening["opening_overlap_frames"] == 0 or opening["median_without_opening_overlap_frames"]:
        raise ValueError("Opening crossing did not realize the diagnostic contrast")
    if barrier["median_without_opening_overlap_frames"] == 0 or barrier["opening_overlap_frames"]:
        raise ValueError("Barrier crossing did not realize the diagnostic contrast")
    return {"format": "c82860-comparison-audit-v1",
            "cases": [request(suffix)["case_id"] for suffix in suffixes],
            "controlled_difference": "median_crossing_location",
            "fixed_context_checked": True,
            "camera_count": len(CAMERAS),
            "diagnostic_geometry_contrast": True,
            "physical_or_legal_acceptance": False}
