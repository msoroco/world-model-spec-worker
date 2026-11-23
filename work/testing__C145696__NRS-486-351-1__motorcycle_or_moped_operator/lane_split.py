"""Source-gated C145696 construction and original-frame passage measurement.

No legal classification follows from the engineering geometry. All distances are
retained as measurements so a reviewer can inspect the source frames.
"""

from __future__ import annotations

import math
import hashlib
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def construction(survey, case):
    """Return a lazy Native spawn/controller request after map and space readback."""
    lanes = survey["lanes"]
    left, right = lanes["left"], lanes["right"]
    require(left["road_id"] == right["road_id"], "different roads")
    require(left["travel_direction"] == right["travel_direction"], "lanes not one-way adjacent")
    require(left["adjacent_right_lane_id"] == right["lane_id"], "left/right lanes not adjacent")
    require(right["adjacent_left_lane_id"] == left["lane_id"], "left/right lanes not adjacent")
    require(left["lane_type"] == right["lane_type"] == "Driving", "non-driving lane")
    require(survey["split_route"]["entry_lane_id"] == left["lane_id"], "route entry lane mismatch")
    require(survey["split_route"]["exit_lane_id"] == right["lane_id"], "route exit lane mismatch")
    require(survey["split_route"]["verified_drivable"], "split route not drivable")
    require(survey["split_route"]["measured_clear_width_m"] > survey["ego_body_width_m"], "no measured passage width")
    require(case["left_motion"] in ("moving", "stationary"), "left motion unknown")
    require(case["right_motion"] in ("moving", "stationary"), "right motion unknown")
    require(case["maneuver"] in ("between", "within_left"), "maneuver unknown")
    require(case["vehicle_class"] in ("motorcycle", "moped"), "chapter vehicle class unknown")
    return {
        "ego_blueprint_class": case["vehicle_class"],
        "ego_role": "motorcycle_or_moped_operator",
        "spawns": [
            {"role": "left_occupant", "lane_id": left["lane_id"], "transform": left["spawn_transform"], "target_motion": case["left_motion"]},
            {"role": "right_occupant", "lane_id": right["lane_id"], "transform": right["spawn_transform"], "target_motion": case["right_motion"]},
            {"role": "ego", "lane_id": left["lane_id"], "transform": survey["ego_spawn_transform"], "target_motion": "moving"},
        ],
        "route": survey["split_route"]["waypoints"] if case["maneuver"] == "between" else survey["left_lane_route"]["waypoints"],
        "controller": {"type": "waypoint_follow", "speed_mps": case["target_speed_mps"], "brake_on_obstruction": True},
        "context_capture": ["ego_classification_source", "operator_identity_source", "police_status_source", "performance_of_duty_source"],
    }


def measure_original(frames, expected):
    """Keep all sampled geometry and reject sparse or substituted actor histories."""
    require(frames, "missing original frames")
    output = []
    prior = None
    for sample in frames:
        frame = sample["frame"]
        require(isinstance(frame, int) and (prior is None or frame == prior + 1), "noncontiguous original frames")
        prior = frame
        actors = sample["actors"]
        require(set(actors) == {"ego", "left_occupant", "right_occupant"}, "missing or extra participant")
        for role, actor in actors.items():
            require(actor["actor_id"] == expected[role]["actor_id"], "actor identity mismatch")
            require(actor["lane_id"] == expected[role]["lane_id"] or role == "ego", "occupant lane mismatch")
            for key in ("s_m", "lateral_m", "half_length_m", "half_width_m", "speed_mps"):
                require(math.isfinite(actor[key]), "nonfinite actor geometry")
            require(actor["half_length_m"] > 0 and actor["half_width_m"] > 0, "invalid body box")
        ego, left, right = actors["ego"], actors["left_occupant"], actors["right_occupant"]
        require(left["lateral_m"] < right["lateral_m"], "lane ordering not retained")
        longitudinal = all(abs(ego["s_m"] - a["s_m"]) <= ego["half_length_m"] + a["half_length_m"] for a in (left, right))
        lateral = left["lateral_m"] + left["half_width_m"] < ego["lateral_m"] < right["lateral_m"] - right["half_width_m"]
        output.append({"frame": frame, "time_s": sample["time_s"], "ego_lane_id": ego["lane_id"],
                       "left_lane_id": left["lane_id"], "right_lane_id": right["lane_id"],
                       "left_speed_mps": left["speed_mps"], "right_speed_mps": right["speed_mps"],
                       "longitudinal_body_overlap": longitudinal, "lateral_between_body_centers": lateral,
                       "candidate_between_frame": longitudinal and lateral,
                       "lateral_clearances_m": [ego["lateral_m"] - ego["half_width_m"] - left["lateral_m"] - left["half_width_m"],
                                                right["lateral_m"] - right["half_width_m"] - ego["lateral_m"] - ego["half_width_m"]]})
    return {"original_frame_count": len(output), "sampled_frames": output,
            "candidate_between_frames": [r["frame"] for r in output if r["candidate_between_frame"]],
            "interpretation": "Physical observations only; no statutory verdict or geometric cutoff"}


def audit_comparison(a, b, difference):
    require(a["assignment_id"] == b["assignment_id"], "assignment mismatch")
    require(a["case_id"] != b["case_id"], "same case")
    require(a["construction_sha256"] and b["construction_sha256"], "missing construction seal")
    require(a["original_frame_count"] >= 2 and b["original_frame_count"] >= 2, "missing original history")
    fixed = ("map_sha256", "road_id", "left_lane_id", "right_lane_id", "ego_class", "camera_plan_sha256", "duration_frames")
    for key in fixed:
        require(a[key] == b[key], f"fixed condition differs: {key}")
    require(a[difference] != b[difference], "declared difference not realized")
    require(a["source_decode_sha256"] and b["source_decode_sha256"], "missing decoded source proof")
    return {"comparison_difference": difference, "fixed_conditions_checked": list(fixed)}


def execute_native(backend, survey, case):
    """Run the constructed setup through a supplied Native backend, with cleanup."""
    request = construction(survey, case)
    owned = []
    try:
        for spawn in request["spawns"]:
            actor = backend.spawn(spawn)
            require(actor is not None, "Native spawn failed")
            owned.append(actor)
        readback = [backend.read_actor(actor) for actor in owned]
        require(len({r["actor_id"] for r in readback}) == 3, "duplicate actor ID")
        for got, wanted in zip(readback, request["spawns"]):
            require(got["lane_id"] == wanted["lane_id"], "spawn lane readback mismatch")
            require(got["role"] == wanted["role"], "spawn role readback mismatch")
        backend.drive_route(owned[2], request["route"], request["controller"])
        return {"actor_readback": readback, "route_waypoints": request["route"], "source_context_required": request["context_capture"]}
    finally:
        for actor in reversed(owned):
            backend.destroy(actor)


def audit_saved(root, receipt, case_id, frame_count):
    """Check exact source seals and complete camera decode before case review."""
    require(receipt["case_id"] == case_id, "case identity mismatch")
    require(receipt["original_frame_count"] == frame_count, "original frame count mismatch")
    require(receipt["frame_map_count"] == frame_count, "frame map count mismatch")
    require(receipt["participant_actor_ids"] and len(set(receipt["participant_actor_ids"].values())) == 3, "participant identities absent")
    require(receipt["police_context_source"] and receipt["operator_identity_source"], "independent operator context absent")
    for key in ("native_result", "frame_map", "original_actor_history"):
        entry = receipt["sources"][key]
        path = Path(root) / entry["path"]
        require(path.is_file() and path.stat().st_size, f"missing source: {key}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], f"stale source: {key}")
    cameras = receipt["camera_decode"]
    require(set(cameras) == {"front", "rear", "left", "right"}, "four cameras required")
    for camera, entry in cameras.items():
        require(entry["decoded_frames"] == frame_count, f"incomplete camera: {camera}")
        require(entry["source_sha256"] and entry["decoder_receipt_sha256"], f"unsealed camera: {camera}")
    require(receipt["actual_pixel_review"]["status"] == "reviewed", "actual pixels unreviewed")
    require(receipt["physical_completion"]["status"] == "reviewed", "physical completion unreviewed")
    return {"case_id": case_id, "audited_original_frames": frame_count, "source_keys": list(receipt["sources"])}
