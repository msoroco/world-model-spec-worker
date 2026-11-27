"""Source-bound original-frame measurements for LVMC 11.16.030.

This module measures the statutory distances and speed. It does not decide
whether a driver had a legally clear and unobstructed view.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FEET_PER_METER = 3.280839895013123
MPH_PER_MPS = 2.2369362920544


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value)


def _source(root, path, digest, name):
    if not isinstance(path, str) or not path:
        raise ValueError("original rail " + name + " source missing or changed")
    relative = Path(path)
    source = (Path(root).resolve() / relative).resolve()
    if (relative.is_absolute() or ".." in relative.parts or
            not source.is_relative_to(Path(root).resolve()) or
            not source.is_file() or source.is_symlink() or
            not _digest(digest) or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
        raise ValueError("original rail " + name + " source missing or changed")
    return source


def read_reviewed_site(root, packet, live_opendrive):
    """Reject a packet that is detached from its reviewed original map bytes."""
    root = Path(root).resolve()
    if packet.get("assignment_id") != root.name and packet.get("assignment_id") != (
            "testing__C410753__LVMC-11-16-030__motor_vehicle_driver"):
        raise ValueError("rail sight assignment identity differs")
    map_ref = packet.get("original_map_source", {})
    review_ref = packet.get("railway_review_source", {})
    for name, ref in (("original map", map_ref), ("railway review", review_ref)):
        relative = Path(ref.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(name + " path escapes attempt")
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file() or source.is_symlink():
            raise ValueError(name + " original source missing")
        if not _digest(ref.get("sha256")) or hashlib.sha256(source.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError(name + " source hash differs")
    if hashlib.sha256(live_opendrive.encode()).hexdigest() != packet.get("road_sha256"):
        raise ValueError("live OpenDRIVE differs from reviewed rail site")
    review = json.loads((root / review_ref["path"]).read_text())
    if (review.get("road_sha256") != packet["road_sha256"] or
            review.get("grade_crossing") is not True or
            review.get("railway_kind") not in ("steam", "electric", "other_motor") or
            review.get("track_extent_each_direction_ft", 0) < 400 or
            review.get("approach_extent_ft", 0) < 100 or
            review.get("municipal_jurisdiction") is not True):
        raise ValueError("reviewed municipal grade-crossing geometry incomplete")
    return review


def measure(root, packet, live_opendrive, frames):
    """Measure source-bound sight rays, crossing speed, and both exceptions."""
    review = read_reviewed_site(root, packet, live_opendrive)
    if len(frames) < 3:
        raise ValueError("original approach and traversal frames missing")
    first = frames[0]
    if type(first.get("original_frame")) is not int:
        raise ValueError("original frame identity missing")
    required = ("time_s", "route_station_m", "speed_mps", "body_on_crossing",
                "sight_crossing_clear", "sight_rail_negative_400ft_clear",
                "sight_rail_positive_400ft_clear", "sight_source_path",
                "sight_source_sha256",
                "flagman_on_duty", "signal_installed", "signal_clearly_visible",
                "signal_immediate_train_approach", "frame_source_path",
                "frame_source_sha256")
    for index, row in enumerate(frames):
        if row.get("original_frame") != first["original_frame"] + index or any(
                key not in row for key in required):
            raise ValueError("original rail frame or required observation missing")
        if not all(isinstance(row[key], (int, float)) and math.isfinite(row[key])
                   for key in ("time_s", "route_station_m", "speed_mps")):
            raise ValueError("original rail time, station or speed invalid")
        if index and (abs(row["time_s"] - frames[index - 1]["time_s"] - .05) > .005 or
                      row["route_station_m"] < frames[index - 1]["route_station_m"]):
            raise ValueError("original 20 Hz rail route join differs")
        frame_source = _source(root, row["frame_source_path"],
                               row["frame_source_sha256"], "frame")
        original = json.loads(frame_source.read_text())
        observed = ("original_frame", "time_s", "route_station_m", "speed_mps",
                    "body_on_crossing", "flagman_on_duty", "signal_installed",
                    "signal_clearly_visible", "signal_immediate_train_approach")
        if any(original.get(key) != row[key] for key in observed):
            raise ValueError("original rail frame readback differs")
        exception_ref = original.get("exception_source_trace")
        if not isinstance(exception_ref, dict):
            raise ValueError("original rail exception source missing")
        exception_source = _source(root, exception_ref.get("path", ""),
                                   exception_ref.get("sha256"), "exception")
        exception = json.loads(exception_source.read_text())
        if (exception.get("frame") != row["original_frame"] or
                any(exception.get(key) != row[key] for key in observed[5:])):
            raise ValueError("original rail exception readback differs")
        source = _source(root, row["sight_source_path"],
                         row["sight_source_sha256"], "sight ray")
        ray = json.loads(source.read_text())
        if (ray.get("frame") != row["original_frame"] or
                [ray.get("crossing"), ray.get("rail_minus_400ft"),
                 ray.get("rail_plus_400ft")] !=
                [row["sight_crossing_clear"], row["sight_rail_negative_400ft_clear"],
                 row["sight_rail_positive_400ft_clear"]]):
            raise ValueError("original rail sight ray readback differs")
        if any(type(row[key]) is not bool for key in
               ("body_on_crossing",) + required[4:7] + required[9:13]):
            raise ValueError("original rail sight or exception state invalid")
    crossing = [i for i, row in enumerate(frames) if row["body_on_crossing"]]
    if not crossing or crossing != list(range(crossing[0], crossing[-1] + 1)):
        raise ValueError("complete continuous grade-crossing traversal missing")
    start_station = frames[crossing[0]]["route_station_m"]
    approach = [row for row in frames[:crossing[0]]
                if 0 < (start_station - row["route_station_m"]) * FEET_PER_METER <= 100]
    if not approach or (start_station - approach[0]["route_station_m"]) * FEET_PER_METER < 95:
        raise ValueError("last 100 feet of original rail approach not covered")
    rays = [(row["sight_crossing_clear"], row["sight_rail_negative_400ft_clear"],
             row["sight_rail_positive_400ft_clear"]) for row in approach]
    speed = [frames[i]["speed_mps"] * MPH_PER_MPS for i in crossing]
    exceptions = {
        "on_duty_flagman_observed": any(frames[i]["flagman_on_duty"] for i in crossing),
        "clearly_visible_nonwarning_signal_observed": any(
            frames[i]["signal_installed"] and frames[i]["signal_clearly_visible"] and
            not frames[i]["signal_immediate_train_approach"] for i in crossing)}
    return {"crossing_original_frames": [frames[i]["original_frame"] for i in crossing],
            "approach_observation_frames": [row["original_frame"] for row in approach],
            "all_three_sight_rays_clear_during_approach": all(all(ray) for ray in rays),
            "any_required_sight_ray_obstructed": any(not all(ray) for ray in rays),
            "traversal_speed_mph_max": max(speed),
            "traversal_speed_mph_min": min(speed),
            "prima_facie_boundary_mph": 15,
            "speed_boundary_relation_observed": (
                "at" if math.isclose(max(speed), 15, abs_tol=1e-9)
                else ("below" if max(speed) < 15 else "above")),
            "exceptions": exceptions, "review_source_sha256": packet["railway_review_source"]["sha256"],
            "legal_visibility_judgment": None, "legal_speed_verdict": None}
