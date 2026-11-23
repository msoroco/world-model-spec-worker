"""Source-bound observations for the nearest-view yield-sign branch.

Visibility samples and sign/marking provenance must come from retained Native
and source-camera evidence. This reports speed and sight points, not whether an
approaching vehicle posed an immediate hazard or whether yielding was adequate.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("approach_history.jsonl", "visibility_samples.json", "visibility_rays.jsonl",
            "road_context.json", "video_frames.jsonl")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path, *, reviewed_context=None) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = (json.loads((root / "road_context.json").read_text())
               if reviewed_context is None else reviewed_context)
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
    rays = _rows(root / "visibility_rays.jsonl")
    ray_by_frame = {row.get("frame"): row for row in rays}
    if len(ray_by_frame) != len(rays) or len(rays) != len(samples):
        raise ValueError("Sight rays do not cover each approach sample once")
    visible = []
    for sample in samples:
        distance = _finite(sample.get("distance_to_intersection_m"), "sight-sample distance")
        if distance < 0 or sample.get("ray_source") != "visibility_rays.jsonl":
            raise ValueError("Visibility sample lacks spatial ray evidence")
        frame = sample.get("frame")
        ray = ray_by_frame.get(frame)
        if (type(frame) is not int or ray is None
                or ray.get("distance_to_intersection_m") != distance
                or not isinstance(ray.get("observer_m"), list)
                or not isinstance(ray.get("target_m"), list)
                or not isinstance(ray.get("blockers"), list)
                or type(ray.get("clear")) is not bool
                or ray["clear"] != (not ray["blockers"])):
            raise ValueError("Visibility sample does not join a complete original ray")
        road_visible = sample.get("through_highway_visible")
        if type(road_visible) is not bool or road_visible != ray["clear"]:
            raise ValueError("Through-highway view differs from original ray")
        ids = sample.get("visible_through_vehicle_ids")
        if not isinstance(ids, list) or ids != ray.get("visible_through_vehicle_ids"):
            raise ValueError("Missing through-traffic visibility result")
        if ids and not road_visible:
            raise ValueError("Visible through vehicle without a through-highway sight path")
        if road_visible:
            visible.append({"frame": frame, "distance_to_intersection_m": distance,
                            "visible_through_vehicle_ids": ids,
                            "ray_source": sample["ray_source"]})
    if not visible:
        raise ValueError("No sourced view of the through highway")
    closest = min(visible, key=lambda sample: sample["distance_to_intersection_m"])
    history, frames = _rows(root / "approach_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(history) < 2 or len(history) > len(frames):
        raise ValueError("Incomplete approach/frame history")
    if {row.get("frame") for row in history} != set(ray_by_frame):
        raise ValueError("Sight rays do not join original approach frames")
    frame_by_id = {row.get("carla_frame"): row for row in frames}
    if len(frame_by_id) != len(frames):
        raise ValueError("Duplicate original camera frame")
    frame_previous = (-1, -math.inf)
    for index, frame in enumerate(frames):
        fid, time = frame.get('carla_frame'), _finite(frame.get('time_s'), 'camera time')
        if (type(fid) is not int or fid <= frame_previous[0] or time <= frame_previous[1]
                or frame.get('video_frame') != index):
            raise ValueError('Nonmonotone original camera frame map')
        frame_previous = (fid, time)
    previous = (-1, -math.inf)
    speed_samples = []
    for row in history:
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = (fid, time)
        frame = frame_by_id.get(fid)
        if frame is None or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        if row.get("road_id") != context["approach_road_id"] or row.get("lane_id") != context["approach_lane_id"]:
            raise ValueError("Ego outside sign-governed approach")
        speed = _finite(row.get("ego_speed_mps"), "ego speed")
        distance = _finite(row.get("distance_to_intersection_m"), "ego distance")
        if speed < 0 or distance < 0:
            raise ValueError("Invalid ego approach sample")
        if distance != ray_by_frame[fid]['distance_to_intersection_m']:
            raise ValueError('Sight ray and original ego distance differ')
        speed_samples.append({"frame": fid, "time_s": time,
                              "ego_speed_mps": speed,
                              "distance_to_intersection_m": distance})
    return {"format": "worker-nearest-view-yield-observations", "sources": sources,
            "intersection_id": context["intersection_id"], "native_yield_sign_id": context["native_yield_sign_id"],
            "closest_sourced_visible_sample": closest,
            "speed_at_closest_view_mps": next(row['ego_speed_mps'] for row in speed_samples
                                              if row['frame'] == closest['frame']),
            "minimum_observed_approach_speed_mps": min(row["ego_speed_mps"] for row in speed_samples),
            "approach_speed_samples": speed_samples,
            "immediate_hazard_judgment": "unresolved; no legal time-to-conflict cutoff",
            "yield_judgment": "unresolved"}
