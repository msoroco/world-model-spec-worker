"""Independent source joins for a signed school-crossing Native attempt.

This module measures an event; it does not decide legal intent or acceptance.
The fixture tests exercise the arithmetic with synthetic records. Production
audit requires sealed original Native files and original camera-frame joins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
EXPECTED_FRAMES = 600
RATE_HZ = 20
MIN_SIGN_ADVANCE_M = 30.48


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(folder: Path, name: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise ValueError("Missing required original source: " + name)
    return path


def read_rows(folder: Path, name: str) -> list[dict]:
    path = source(folder, name)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != EXPECTED_FRAMES:
        raise ValueError("Incomplete original source: " + name)
    return rows


def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Invalid original number: " + name)
    return float(value)


def validate_geometry(geometry: dict) -> dict:
    crossing = geometry.get("crosswalk", {})
    sign = geometry.get("school_xing_sign", {})
    near = finite_number(crossing.get("near_x_m"), "crosswalk near edge")
    width = finite_number(crossing.get("width_along_road_m"), "crosswalk width")
    low_y = finite_number(crossing.get("low_y_m"), "crosswalk low y")
    high_y = finite_number(crossing.get("high_y_m"), "crosswalk high y")
    sign_x = finite_number(sign.get("x_m"), "sign x")
    if width <= 0 or low_y >= 0 or high_y <= 0:
        raise ValueError("Native crosswalk geometry differs")
    if sign.get("legend") != "School-Xing" or sign.get("native_map_object_present") is not True:
        raise ValueError("Native School-Xing map object source absent")
    if near - sign_x < MIN_SIGN_ADVANCE_M:
        raise ValueError("School-Xing advance distance below 100 ft")
    if crossing.get("marked_yellow") is not True:
        raise ValueError("Yellow school-crossing marking source absent")
    if geometry.get("native_map_sha256") is None or geometry.get("native_map_object_readback") is not True:
        raise ValueError("Original Native geometry readback absent")
    return {"near_x_m": near, "far_x_m": near + width, "low_y_m": low_y,
            "high_y_m": high_y, "sign_advance_m": near - sign_x}


def measure_rows(native: list[dict], mapping: list[dict], geometry: dict,
                 *, require_original: bool = True) -> dict:
    """Measure first vehicle-body entry and person state at that same frame."""
    bounds = validate_geometry(geometry)
    if len(native) != EXPECTED_FRAMES or len(mapping) != EXPECTED_FRAMES:
        raise ValueError("Incomplete synchronized Native and camera source")
    prior_frame = -1
    prior_front = None
    entry = None
    for index, (sample, joined) in enumerate(zip(native, mapping)):
        frame = sample.get("native_frame")
        timestamp = finite_number(sample.get("time_s"), "Native time")
        if type(frame) is not int or frame <= prior_frame or joined.get("native_frame") != frame:
            raise ValueError("Original Native frame join differs")
        if joined.get("video_frame") != index or abs(
            finite_number(joined.get("time_s"), "camera time") - timestamp) > 1e-4:
            raise ValueError("Original Native camera time join differs")
        camera_frames = joined.get("camera_frames", {})
        if set(camera_frames) != set(CAMERAS) or any(camera_frames[k] != frame for k in CAMERAS):
            raise ValueError("Four original camera frame joins differ")
        if require_original and sample.get("source_kind") != "original_native_actor_readback":
            raise ValueError("Authored or synthetic sample cannot prove Native entry")
        body = sample.get("ego_body_xy_m", [])
        if len(body) != 4:
            raise ValueError("Original ego footprint is incomplete")
        front = max(finite_number(point[0], "ego footprint x") for point in body)
        for point in body:
            finite_number(point[1], "ego footprint y")
        person = sample.get("person", {})
        if person.get("actor_id") is None or person.get("actor_kind") != "walker":
            raise ValueError("Original pedestrian actor source absent")
        ped_x = finite_number(person.get("center_x_m"), "person x")
        ped_y = finite_number(person.get("center_y_m"), "person y")
        velocity_y = finite_number(person.get("velocity_y_mps"), "person y velocity")
        in_crosswalk = bounds["near_x_m"] <= ped_x <= bounds["far_x_m"] and (
            bounds["low_y_m"] <= ped_y <= bounds["high_y_m"])
        on_approach_side = ped_y < 0
        if prior_front is not None and prior_front < bounds["near_x_m"] <= front and entry is None:
            entry = {"native_frame": frame, "video_frame": index, "time_s": timestamp,
                     "ego_front_x_m": front, "person_in_crosswalk": in_crosswalk,
                     "person_on_approach_side": on_approach_side,
                     "person_approach_motion_observed": velocity_y > 0,
                     "person_actor_id": person["actor_id"]}
        prior_frame = frame
        prior_front = front
    if entry is None:
        raise ValueError("No original ego front entry across crosswalk edge")
    rear = min(finite_number(point[0], "ego final rear x") for point in native[-1]["ego_body_xy_m"])
    return {"format": "c394563-school-crossing-measurement-v1", "entry": entry,
            "sign_advance_m": bounds["sign_advance_m"],
            "ego_rear_cleared_crosswalk": rear > bounds["far_x_m"],
            "intent_from_motion_only": True, "official_marking_verified": False,
            "actual_pixels_verified": False, "sign_display_verified": False,
            "physical_completion_claimed": False,
            "legal_verdict": None}


def audit_case(attempt: Path, case_id: str) -> dict:
    config = json.loads(source(attempt, "config.json").read_text())
    if config.get("case_id") != case_id or config.get("rate_hz") != RATE_HZ or (
        config.get("duration_frames") != EXPECTED_FRAMES):
        raise ValueError("Exact school-crossing case or duration differs")
    geometry_path = source(attempt, "road_geometry.json")
    geometry = json.loads(geometry_path.read_text())
    native = read_rows(attempt, "native_samples.jsonl")
    mapping = read_rows(attempt, "video_frames.jsonl")
    report = measure_rows(native, mapping, geometry)
    report["case_id"] = case_id
    report["sources"] = {name: sha(source(attempt, name)) for name in (
        "config.json", "road_geometry.json", "native_samples.jsonl", "video_frames.jsonl")}
    return report


def audit_comparison(first: dict, second: dict) -> dict:
    if first.get("format") != second.get("format") or first.get("case_id") == second.get("case_id"):
        raise ValueError("Comparison requires two distinct measured cases")
    if first.get("sign_advance_m") != second.get("sign_advance_m"):
        raise ValueError("Comparison changed fixed school-crossing sign geometry")
    a, b = first["entry"], second["entry"]
    fixed = ("person_actor_id", "person_on_approach_side")
    if any(a.get(k) != b.get(k) for k in fixed):
        raise ValueError("Comparison changed fixed pedestrian identity or approach side")
    if not (a.get("person_in_crosswalk") is True and b.get("person_in_crosswalk") is False):
        raise ValueError("Comparison lacks occupied versus cleared entry")
    return {"format": "c394563-school-crossing-comparison-v1",
            "case_ids": [first["case_id"], second["case_id"]],
            "declared_difference": "same-side-person-occupancy-at-vehicle-entry",
            "fixed_sign_advance_m": first["sign_advance_m"],
            "legal_verdict": None, "physical_completion_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_case(args.attempt, args.case), sort_keys=True))


if __name__ == "__main__":
    main()
