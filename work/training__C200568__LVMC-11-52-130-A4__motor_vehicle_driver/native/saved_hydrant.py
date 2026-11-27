"""Join saved hydrant survey, pose and video frame sources without legal inference."""

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "training__C200568__LVMC-11-52-130-A4__motor_vehicle_driver"
SOURCES = ("hydrant-trace.jsonl", "video_frames.jsonl", "hydrant_survey.json")
FRAMES = 600
FT_PER_M = 3.280839895013123


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def gap_to_rotated_footprint_ft(point, center, extent, yaw_deg):
    if len(point) < 2 or len(center) < 2 or len(extent) < 2:
        raise ValueError("Vehicle body extent or hydrant position missing")
    values = [*point[:2], *center[:2], *extent[:2], yaw_deg]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError("Finite hydrant and vehicle geometry required")
    if extent[0] <= 0 or extent[1] <= 0:
        raise ValueError("Vehicle body extent missing")
    theta = math.radians(yaw_deg)
    dx, dy = point[0] - center[0], point[1] - center[1]
    local_x = dx * math.cos(theta) + dy * math.sin(theta)
    local_y = -dx * math.sin(theta) + dy * math.cos(theta)
    return math.hypot(max(abs(local_x) - extent[0], 0),
                      max(abs(local_y) - extent[1], 0)) * FT_PER_M


def join(attempt, config, *, allow_fixture=False):
    attempt = Path(attempt)
    case_id = config.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Exact selected case differs")
    paths = {name: attempt / name for name in SOURCES}
    if any(not path.is_file() for path in paths.values()):
        missing = next(name for name, path in paths.items() if not path.is_file())
        raise ValueError("Missing required source: " + missing)
    hashes = {name: sha(path) for name, path in paths.items()}
    trace, mapping = (rows(paths[name]) for name in SOURCES[:2])
    survey = json.loads(paths[SOURCES[2]].read_text())
    if len(trace) != FRAMES or len(mapping) != FRAMES:
        raise ValueError("Full 600-frame source and frame map required")
    kind = "synthetic_native_sample" if allow_fixture else "original_native_observation"
    if survey.get("source_kind") != ("synthetic_native_sample" if allow_fixture else
                                     "original_native_hydrant_survey"):
        raise ValueError("Hydrant survey provenance differs")
    if not survey.get("parking_permission_source") or not survey.get("hydrant_identity_source") or \
            not survey.get("premises_access_source") or \
            survey.get("parking_permission") != config.get("parking_permission"):
        raise ValueError("Original parking permission or hydrant source differs")
    if len(survey.get("hydrant_xyz_m", [])) != 3:
        raise ValueError("Original hydrant geometry missing")
    uncertainty = survey.get("distance_uncertainty_ft")
    if not isinstance(uncertainty, (int, float)) or not math.isfinite(uncertainty) or uncertainty < 0:
        raise ValueError("Distance uncertainty source missing")
    distance, prior_native, vehicle_id, hydrant_id = [], None, None, None
    for i, (row, frame_map) in enumerate(zip(trace, mapping)):
        native = row.get("native_frame")
        if row.get("source_kind") != kind or row.get("frame") != i or \
                row.get("video_frame") != i or frame_map.get("video_frame") != i or \
                frame_map.get("native_frame") != native or \
                frame_map.get("carla_frame") != native or \
                row.get("time_s") != frame_map.get("time_s") or \
                abs(row.get("time_s", -100) - i / 20) > 1e-6:
            raise ValueError("Original Native, video and time join differs")
        if type(native) is not int or (prior_native is not None and native <= prior_native):
            raise ValueError("Original Native frame sequence differs")
        prior_native = native
        if row.get("parking_permission_source") != survey["parking_permission_source"] or \
                row.get("hydrant_identity_source") != survey["hydrant_identity_source"] or \
                row.get("hydrant_xyz_m") != survey["hydrant_xyz_m"]:
            raise ValueError("Original permission and hydrant survey join differs")
        if row.get("exception_context") != config.get("exception_context") or \
                row.get("exception_source_verified") is not False:
            raise ValueError("Exception context cannot be inferred from geometry")
        if vehicle_id is None:
            vehicle_id, hydrant_id = row.get("ego_actor_id"), row.get("hydrant_actor_id")
        if row.get("ego_actor_id") != vehicle_id or row.get("hydrant_actor_id") != hydrant_id or \
                type(vehicle_id) is not int or type(hydrant_id) is not int or \
                vehicle_id == hydrant_id:
            raise ValueError("Fixed distinct original actors required")
        speed = row.get("ego_speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed > 0.05:
            raise ValueError("Full stopped interval source missing")
        distance.append(gap_to_rotated_footprint_ft(survey["hydrant_xyz_m"],
                        row.get("ego_xyz_m", []), row.get("ego_extent_xyz_m", []),
                        row.get("ego_yaw_deg")))
    closest = min(distance)
    threshold = 15 if config["parking_permission"] == "parallel_permitted" else 20
    bracket = [max(0, closest - uncertainty), closest + uncertainty]
    relation = "inside" if bracket[1] < threshold else \
        "outside" if bracket[0] > threshold else "overlaps"
    return {"case_id": case_id, "frames": FRAMES, "source_kind": kind,
            "source_hashes": hashes, "parking_permission": config["parking_permission"],
            "applicable_threshold_ft": threshold,
            "closest_footprint_distance_ft": closest,
            "distance_bracket_ft": bracket, "threshold_relation": relation,
            "requested_clearance_ft": config["requested_clearance_ft"],
            "requested_target_confirmed": abs(closest - config["requested_clearance_ft"]) <= uncertainty,
            "exception_context_declaration": config["exception_context"],
            "exception_source_verified": False,
            "paint_or_sign_used_to_select_threshold": False,
            "original_native_observed": not allow_fixture,
            "legal_verdict_claimed": False}
