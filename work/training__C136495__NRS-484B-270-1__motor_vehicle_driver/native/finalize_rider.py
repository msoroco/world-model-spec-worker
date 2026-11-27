"""Saved-only, source-bound rider movement measurement.

This processor reports measurements and unresolved legal questions. It does not
infer intentional interference, lawful riding, or causation from proximity.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from scene import fixed_context

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing numeric Native source: " + name)
    return float(value)


def finalize(folder: str | Path) -> dict:
    folder = Path(folder)
    manifest = json.loads((folder / "source-manifest.json").read_text())
    if manifest.get("format") != "c136495-native-source-manifest-v1":
        raise ValueError("Wrong rider source manifest")
    if manifest.get("condition") not in ("clear", "intrusion"):
        raise ValueError("Wrong comparison condition")
    if manifest.get("candidate_id") not in ("primary", "fallback1"):
        raise ValueError("Wrong selected candidate provenance")
    if manifest.get("fixed_context") != fixed_context():
        raise ValueError("Fixed source context differs from authored construction")
    if manifest.get("case_id", "").rsplit("__", 1)[-1] != (
        "probe_a" if manifest["condition"] == "clear" else "probe_b"
    ):
        raise ValueError("Wrong exact case identity")
    files = manifest.get("sha256", {})
    required = ("actor-frames.jsonl", "camera-frame-map.jsonl", "classification.json")
    if set(files) != set(required):
        raise ValueError("Missing required source inventory")
    for name in required:
        path = folder / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        if sha256(path) != files[name]:
            raise ValueError("Original source hash differs: " + name)
    classification = json.loads((folder / "classification.json").read_text())
    if classification.get("driver_actor_role") != "motor_vehicle_driver":
        raise ValueError("Missing motor-vehicle driver classification source")
    if classification.get("rider_vehicle_type") != "bicycle":
        raise ValueError("Missing bicycle classification source")
    if classification.get("rider_lawful_status") not in ("unresolved", "source_review_required"):
        raise ValueError("Unsupported lawful-riding assertion")
    if classification.get("driver_intent") != "unresolved":
        raise ValueError("Unsupported intent assertion")
    widths = classification.get("observed_body_width_m", {})
    ego_width = _number(widths.get("ego"), "ego body width")
    rider_width = _number(widths.get("rider"), "rider body width")
    lengths = classification.get("observed_body_length_m", {})
    ego_length = _number(lengths.get("ego"), "ego body length")
    rider_length = _number(lengths.get("rider"), "rider body length")
    if not (.4 < ego_width < 4 and .2 < rider_width < 2):
        raise ValueError("Native body dimensions outside diagnostic bounds")
    if not (1 < ego_length < 10 and .5 < rider_length < 4):
        raise ValueError("Native body lengths outside diagnostic bounds")
    rows = [json.loads(line) for line in (folder / required[0]).read_text().splitlines()]
    camera_rows = [json.loads(line) for line in (folder / required[1]).read_text().splitlines()]
    if len(rows) != 600 or len(camera_rows) != 600:
        raise ValueError("Missing 600-frame original source")
    first_frame = rows[0].get("native_frame")
    if type(first_frame) is not int:
        raise ValueError("Missing original first frame identity")
    min_gap = math.inf
    max_abs_rider_yaw_rate = 0.0
    max_rider_deceleration = 0.0
    near_frames = 0
    longitudinal_interaction_frames = 0
    first_longitudinal_overlap = None
    min_abs_longitudinal_offset = math.inf
    first_ego_lateral_change = None
    first_rider_speed_drop = None
    first_rider_yaw_change = None
    previous_speed = None
    previous_yaw = None
    for index, (row, cameras) in enumerate(zip(rows, camera_rows)):
        frame = first_frame + index
        if row.get("native_frame") != frame or cameras.get("native_frame") != frame:
            raise ValueError("Original frame join differs")
        expected_time = index / 20.0
        if abs(_number(row.get("time_s"), "actor time") - expected_time) > .051:
            raise ValueError("Original actor time join differs")
        if abs(_number(cameras.get("time_s"), "camera time") - row["time_s"]) > .051:
            raise ValueError("Original camera time join differs")
        if set(cameras.get("camera_frames", {})) != set(CAMERAS):
            raise ValueError("Four original camera sources missing")
        if any(cameras["camera_frames"][name] != frame for name in CAMERAS):
            raise ValueError("Original camera frame identity differs")
        actors = row.get("actors", {})
        if set(actors) != {"ego", "rider"}:
            raise ValueError("Distinct original actor source missing")
        ego, rider = actors["ego"], actors["rider"]
        ego_y = _number(ego.get("y_m"), "ego lateral pose")
        rider_y = _number(rider.get("y_m"), "rider lateral pose")
        rider_speed = _number(rider.get("speed_mps"), "rider speed")
        rider_yaw = _number(rider.get("yaw_rad"), "rider yaw")
        ego_x = _number(ego.get("x_m"), "ego longitudinal pose")
        rider_x = _number(rider.get("x_m"), "rider longitudinal pose")
        gap = abs(rider_y - ego_y) - (ego_width + rider_width) / 2
        abs_offset = abs(rider_x - ego_x)
        min_abs_longitudinal_offset = min(min_abs_longitudinal_offset, abs_offset)
        body_overlap = abs_offset <= (ego_length + rider_length) / 2
        if body_overlap and first_longitudinal_overlap is None:
            first_longitudinal_overlap = frame
        if abs_offset <= (ego_length + rider_length) / 2 + 5:
            longitudinal_interaction_frames += 1
            min_gap = min(min_gap, gap)
            near_frames += gap < .5  # Engineering review band, not legal threshold.
        if first_ego_lateral_change is None and abs(ego_y + 1.1) > .1:
            first_ego_lateral_change = frame
        if previous_speed is not None:
            deceleration = (previous_speed - rider_speed) * 20
            max_rider_deceleration = max(max_rider_deceleration, deceleration)
            if first_rider_speed_drop is None and previous_speed - rider_speed > .05:
                first_rider_speed_drop = frame
        if previous_yaw is not None:
            delta = math.atan2(math.sin(rider_yaw - previous_yaw),
                               math.cos(rider_yaw - previous_yaw))
            rate = abs(delta * 20)
            max_abs_rider_yaw_rate = max(max_abs_rider_yaw_rate, rate)
            if first_rider_yaw_change is None and rate > .02:
                first_rider_yaw_change = frame
        previous_speed, previous_yaw = rider_speed, rider_yaw
    if not longitudinal_interaction_frames:
        raise ValueError("Original actors never entered the planned interaction window")
    return {"format": "c136495-saved-rider-measurements-v1",
            "case_id": manifest["case_id"], "condition": manifest["condition"],
            "candidate_id": manifest["candidate_id"],
            "source_sha256": files, "first_native_frame": first_frame,
            "frame_count": 600, "camera_names": list(CAMERAS),
            "minimum_lateral_surface_gap_m": round(min_gap, 6),
            "near_frames_engineering_band": near_frames,
            "longitudinal_interaction_frames": longitudinal_interaction_frames,
            "first_longitudinal_body_overlap_frame": first_longitudinal_overlap,
            "minimum_abs_longitudinal_offset_m": round(min_abs_longitudinal_offset, 6),
            "first_ego_lateral_change_frame": first_ego_lateral_change,
            "first_rider_speed_drop_frame": first_rider_speed_drop,
            "first_rider_yaw_change_frame": first_rider_yaw_change,
            "maximum_rider_deceleration_mps2": round(max_rider_deceleration, 6),
            "maximum_abs_rider_yaw_rate_rps": round(max_abs_rider_yaw_rate, 6),
            "rider_lawful_status": "unresolved", "driver_intent": "unresolved",
            "causal_interference": "unresolved", "legal_verdict_claimed": False,
            "physical_native_verified": False}
