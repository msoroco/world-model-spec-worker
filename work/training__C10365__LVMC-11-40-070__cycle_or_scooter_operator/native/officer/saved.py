"""Saved-frame joins and measurements; never promote a requested cue to an observation."""
import json
import math
from pathlib import Path

from check import check

FRAMES = 480
RATE = 20


def read_rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def process(bundle, raw, video, review, *, synthetic=False):
    bundle = Path(bundle)
    checked = check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw_rows, video_rows = read_rows(raw), read_rows(video)
    visual = json.loads(Path(review).read_text())
    if len(raw_rows) != FRAMES or len(video_rows) != FRAMES:
        raise ValueError("480 source frames required")
    if visual.get("source_kind") != ("synthetic_fixture" if synthetic else "original_native_review"):
        raise ValueError("Review source kind mismatch")
    if visual.get("case_id") != cfg["case_id"] or visual.get("candidate_id") != cfg["candidate_id"]:
        raise ValueError("Review identity mismatch")
    if not synthetic:
        for name in ("overview.mkv", "rider_forward.mkv", "officer_side.mkv"):
            if not (Path(raw).parent / name).is_file():
                raise ValueError("Original FFV1 camera missing: " + name)
        map_path = Path(raw).parent / "native-map-readback.json"
        if not map_path.is_file():
            raise ValueError("Original Native map readback missing")
        mapping = json.loads(map_path.read_text())
        if (mapping.get("stop_landmark_readback", {}).get("id") != "3651" or
                mapping.get("stop_landmark_readback", {}).get("road_id") != 365):
            raise ValueError("Original device readback mismatch")
    speeds, front_x, rider_ids, officer_ids = [], [], set(), set()
    for i, (row, v) in enumerate(zip(raw_rows, video_rows)):
        if row.get("frame") != i or v.get("video_frame") != i:
            raise ValueError("Frame sequence changed")
        if row.get("native_frame") != v.get("native_frame") or \
                row.get("time_s") != v.get("time_s"):
            raise ValueError("Native/video time join changed")
        if row.get("source_kind") != ("synthetic_fixture" if synthetic else "original_native"):
            raise ValueError("Raw source kind mismatch")
        rider, officer = row.get("rider", {}), row.get("officer_actor", {})
        if rider.get("blueprint") != cfg["rider_blueprint"] or \
                not str(officer.get("blueprint", "")).startswith("walker.pedestrian."):
            raise ValueError("Rider/officer actor class mismatch")
        if row.get("observed_road_id") != 365 or row.get("observed_lane_id") != -1:
            raise ValueError("Rider approach lane mismatch")
        if row.get("officer_cue_requested") != cfg["officer_cue_requested"]:
            raise ValueError("Officer request identity changed")
        rider_ids.add(rider.get("actor_id"))
        officer_ids.add(officer.get("actor_id"))
        speed = rider.get("speed_mps")
        vertices = rider.get("body_native_xyz_m")
        if not finite_number(speed) or speed < 0 or \
                not isinstance(vertices, list) or len(vertices) < 4 or \
                not all(isinstance(p, list) and len(p) == 3 and all(map(finite_number, p))
                        for p in vertices):
            raise ValueError("Original body or speed invalid")
        speeds.append(speed)
        front_x.append(max(p[0] for p in vertices))
    if len(rider_ids) != 1 or len(officer_ids) != 1 or None in rider_ids | officer_ids:
        raise ValueError("Actor identity discontinuity")
    if rider_ids == officer_ids:
        raise ValueError("Rider/officer actor identity collapsed")
    stop_runs, current = [], 0
    for speed, front in zip(speeds, front_x):
        current = current + 1 if speed <= .25 and front < 50 else 0
        stop_runs.append(current)
    stopped = max(stop_runs) >= RATE
    crossing_frame = next((i for i, front in enumerate(front_x) if front > 50), None)
    if crossing_frame is not None and crossing_frame == 0:
        raise ValueError("No pre-crossing approach")
    reviewed = visual.get("reviewed_frames")
    if not isinstance(reviewed, list) or not reviewed or \
            any(type(i) is not int or i < 0 or i >= FRAMES for i in reviewed):
        raise ValueError("Visual review frame references invalid")
    if visual.get("device_id") != "3651" or visual.get("device_applicable") is not True:
        raise ValueError("Device applicability unreviewed")
    if visual.get("rider_class") != "bicycle":
        raise ValueError("Rider class unreviewed")
    if visual.get("officer_actor_id") != next(iter(officer_ids)):
        raise ValueError("Officer review actor join")
    direction = visual.get("officer_direction")
    if cfg["case_id"].endswith("probe_a"):
        if direction != "none_contrary" or not stopped or crossing_frame is not None:
            raise ValueError("Ordinary device response not demonstrated")
    else:
        if (direction != "proceed" or visual.get("officer_authority_reviewed") is not True or
                visual.get("direction_visible") is not True or crossing_frame is None or
                min(reviewed) >= crossing_frame):
            raise ValueError("Contrary officer direction and response not demonstrated")
    if not synthetic and visual.get("reviewer") in (None, "", "synthetic"):
        raise ValueError("Independent original visual reviewer missing")
    margin = min(50 - f for f, s in zip(front_x, speeds) if s <= .25) \
        if stopped else None
    first_approach = next((i for i, f in enumerate(front_x) if f >= 40), None)
    latency = ((crossing_frame - first_approach) / RATE
               if crossing_frame is not None and first_approach is not None else None)
    separation = min(math.hypot(row["rider"]["center_native_xyz_m"][0] -
                                row["officer_actor"]["center_native_xyz_m"][0],
                                row["rider"]["center_native_xyz_m"][1] -
                                row["officer_actor"]["center_native_xyz_m"][1])
                     for row in raw_rows)
    visibility = visual.get("officer_cue_visibility")
    if not finite_number(visibility) or not 0 <= visibility <= 1:
        raise ValueError("Visibility measurement invalid")
    triggers = {
        "fallback1": margin is not None and margin < 3 or
                     latency is not None and latency < 2,
        "fallback2": visibility < .90,
        "fallback3": separation < 5,
    }
    return {
        "case_id": checked["case_id"], "candidate_id": checked["candidate_id"],
        "source_kind": "synthetic_fixture" if synthetic else "original_native",
        "frames": FRAMES, "stopped": stopped, "crossing_frame": crossing_frame,
        "stop_margin_m": margin, "crossing_latency_s": latency,
        "min_officer_rider_separation_m": separation,
        "officer_cue_visibility": visibility, "fallback_triggers": triggers,
        "officer_direction_reviewed": direction,
        "physical_legal_verdict": None, "delivery_ready": False,
    }
