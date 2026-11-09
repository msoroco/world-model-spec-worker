"""CPU-side construction and measurement helpers for the C101303 lane change.

The CARLA adapter must supply measured waypoint and actor states. No legal
following-distance threshold is inferred here.
"""
import hashlib
import json
import math
from pathlib import Path


def choose_crest(candidates, *, min_rise_m=0.4, max_lane_gap_m=5.0):
    """Return a connected two-lane candidate with a measured rise and fall."""
    for item in candidates:
        left = item["initial_lane"]
        right = item["target_lane"]
        if len(left) < 3 or len(right) != len(left):
            continue
        if any(not sample.get("driving", False) for sample in left + right):
            continue
        if any(left[i]["road_id"] != right[i]["road_id"] for i in range(len(left))):
            continue
        if any(abs(left[i]["x"] - right[i]["x"]) > max_lane_gap_m for i in range(len(left))):
            continue
        heights = [sample["z"] for sample in left]
        peak = max(range(1, len(heights) - 1), key=heights.__getitem__)
        if heights[peak] - heights[0] >= min_rise_m and heights[peak] - heights[-1] >= min_rise_m:
            return item
    raise ValueError("No measured connected two-lane hill crest in supplied waypoints")


def lane_change_schedule(time_s, *, lane_change_at_s=6.0):
    """The lead remains in the initial lane during the following window."""
    if time_s < 0:
        raise ValueError("Negative simulation time")
    return {"lead_lane": "initial", "ego_lane": "initial" if time_s < lane_change_at_s else "target",
            "following_window": time_s < lane_change_at_s}


def measure_following(rows, *, lane_change_at_s=6.0, expected_hz=20):
    """Summarize observed following samples; do not assign a legal outcome."""
    if not rows:
        raise ValueError("Missing actor-state samples")
    measurements = []
    last_frame = None
    for row in rows:
        frame = row["frame"]
        if last_frame is not None and frame != last_frame + 1:
            raise ValueError("Nonconsecutive actor-state frames")
        last_frame = frame
        if not math.isclose(row["time_s"], frame / expected_hz, abs_tol=0.051):
            raise ValueError("Actor-state time/frame mismatch")
        if row["time_s"] >= lane_change_at_s:
            continue
        if row["ego_lane_id"] != row["lead_lane_id"]:
            raise ValueError("No same-lane following during declared interval")
        gap = row["lead_rear_s_m"] - row["ego_front_s_m"]
        if not math.isfinite(gap):
            raise ValueError("Nonfinite vehicle separation")
        measurements.append({"frame": frame, "time_s": row["time_s"],
                             "bumper_gap_m": gap, "ego_speed_mps": row["ego_speed_mps"],
                             "lead_speed_mps": row["lead_speed_mps"]})
    if not measurements:
        raise ValueError("No following samples before lane change")
    return {"following_samples": measurements, "minimum_observed_gap_m":
            min(sample["bumper_gap_m"] for sample in measurements),
            "legal_judgment": None}


def finalize_saved(attempt):
    """Read original saved evidence and bind the measurement to source bytes."""
    attempt = Path(attempt)
    names = ("actor_states.jsonl", "road_profile.json", "surface_context.json",
             "traffic_context.json", "video_frames.jsonl")
    sources = {}
    for name in names:
        source = attempt / name
        if not source.is_file():
            raise ValueError("Missing required source: " + name)
        sources[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = [json.loads(line) for line in (attempt / names[0]).read_text().splitlines() if line]
    frame_map = [json.loads(line) for line in (attempt / names[-1]).read_text().splitlines() if line]
    map_by_frame = {row["carla_frame"]: row["time_s"] for row in frame_map}
    if len(map_by_frame) != len(frame_map) or any(
            row["frame"] not in map_by_frame or
            not math.isclose(row["time_s"], map_by_frame[row["frame"]], abs_tol=1e-4)
            for row in rows):
        raise ValueError("Original actor-state/frame-map join failed")
    road = json.loads((attempt / names[1]).read_text())
    surface = json.loads((attempt / names[2]).read_text())
    traffic = json.loads((attempt / names[3]).read_text())
    if not road.get("public_highway_evidence") or not surface.get("condition") or not isinstance(traffic.get("participants"), list):
        raise ValueError("Missing highway, surface or traffic context")
    result = measure_following(rows)
    result.update(source_sha256=sources, highway_context=road["public_highway_evidence"],
                  surface_condition=surface["condition"], traffic_participants=traffic["participants"])
    return result
