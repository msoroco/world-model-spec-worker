"""Source-bound observations for the nearest-view yield-sign branch.

Visibility samples and sign/marking provenance must come from retained Native
and source-camera evidence. This reports speed and sight points, not whether an
approaching vehicle posed an immediate hazard or whether yielding was adequate.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("approach_history.jsonl", "visibility_samples.json", "road_context.json",
            "video_frames.jsonl")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "approach_road_id",
                "approach_lane_id", "through_highway_id", "native_yield_sign_id",
                "sign_governance_source", "marking_inventory_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced road/sign context: " + key)
    if context.get("no_stop_line") is not True or context.get("no_near_crosswalk") is not True:
        raise ValueError("Nearest-view branch needs sourced absence of stop line and crosswalk")
    if context.get("police_control") is not False or context.get("traffic_signal_control") is not False:
        raise ValueError("Control exception not excluded by source context")
    samples = json.loads((root / "visibility_samples.json").read_text())
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError("Insufficient approach visibility samples")
    visible = []
    for sample in samples:
        distance = _finite(sample.get("distance_to_intersection_m"), "sight-sample distance")
        if distance < 0 or not sample.get("ray_source"):
            raise ValueError("Visibility sample lacks spatial ray evidence")
        ids = sample.get("visible_through_vehicle_ids")
        if not isinstance(ids, list):
            raise ValueError("Missing through-traffic visibility result")
        if ids:
            visible.append({"distance_to_intersection_m": distance,
                            "visible_through_vehicle_ids": ids,
                            "ray_source": sample["ray_source"]})
    if not visible:
        raise ValueError("No sourced view of through traffic")
    closest = min(visible, key=lambda sample: sample["distance_to_intersection_m"])
    history, frames = _rows(root / "approach_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(history) < 2 or len(history) != len(frames):
        raise ValueError("Incomplete approach/frame history")
    previous = (-1, -math.inf)
    speed_samples = []
    for index, (row, frame) in enumerate(zip(history, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        if row.get("road_id") != context["approach_road_id"] or row.get("lane_id") != context["approach_lane_id"]:
            raise ValueError("Ego outside sign-governed approach")
        speed = _finite(row.get("ego_speed_mps"), "ego speed")
        distance = _finite(row.get("distance_to_intersection_m"), "ego distance")
        if speed < 0 or distance < 0:
            raise ValueError("Invalid ego approach sample")
        speed_samples.append({"frame": fid, "time_s": time,
                              "ego_speed_mps": speed,
                              "distance_to_intersection_m": distance})
    return {"format": "worker-nearest-view-yield-observations", "sources": sources,
            "intersection_id": context["intersection_id"], "native_yield_sign_id": context["native_yield_sign_id"],
            "closest_sourced_visible_sample": closest,
            "minimum_observed_approach_speed_mps": min(row["ego_speed_mps"] for row in speed_samples),
            "approach_speed_samples": speed_samples,
            "immediate_hazard_judgment": "unresolved; no legal time-to-conflict cutoff",
            "yield_judgment": "unresolved"}
