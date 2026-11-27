"""Raw three-dimensional left-arm upward diagnostic for the NRS 484B.420 reference.

Numerical pose margins are engineering diagnostics, not statutory cutoffs.
"""
from __future__ import annotations

from math import cos, hypot, isfinite, radians, sin


def _point(row, name):
    point = row.get("bone_world_xyz_m", {}).get(name)
    if not isinstance(point, list) or len(point) != 3 or not all(
        type(value) in (int, float) and isfinite(value) for value in point
    ):
        raise ValueError(f"Original world bone position missing: {name}")
    return point


def measure_left_upward(rows, *, rider_id, bicycle_id, source_packet):
    """Join source-bound 20-Hz arm readback to a rider and bicycle."""
    if len(rows) != 600 or source_packet.get("kind") != "original_native_arm_readback":
        raise ValueError("Original 600-frame arm readback source required")
    if source_packet.get("rider_actor_id") != rider_id or source_packet.get("bicycle_actor_id") != bicycle_id:
        raise ValueError("Rider and bicycle source identities differ")
    runs = []
    for frame, row in enumerate(rows):
        if (row.get("frame") != frame or row.get("rider_actor_id") != rider_id or
                row.get("bicycle_actor_id") != bicycle_id or
                row.get("bicycle_blueprint") != "vehicle.bh.crossbike"):
            raise ValueError("Original rider, bicycle or frame join differs")
        if abs(float(row.get("time_s", -1)) - frame / 20) > 1e-8:
            raise ValueError("Original arm time join differs")
        if type(row.get("roadway_occupied")) is not bool or type(row.get("on_right_turn_route")) is not bool:
            raise ValueError("Original roadway or route context missing")
        if row.get("requested_method") not in ("left_upward", "right_horizontal", "none"):
            raise ValueError("Unknown requested method in arm source")
        shoulder = _point(row, "crl_shoulder__L")
        elbow = _point(row, "crl_foreArm__L")
        wrist = _point(row, "crl_hand__L")
        yaw = radians(float(row.get("bicycle_yaw_deg", float("nan"))))
        if not isfinite(yaw):
            raise ValueError("Original bicycle heading missing")
        left_x, left_y = -sin(yaw), cos(yaw)
        leftward = (wrist[0] - shoulder[0]) * left_x + (wrist[1] - shoulder[1]) * left_y
        upward = wrist[2] - shoulder[2]
        elbow_upward = elbow[2] - shoulder[2]
        arm_length = hypot(hypot(wrist[0] - shoulder[0], wrist[1] - shoulder[1]), upward)
        if not 0.15 <= arm_length <= 1.2:
            raise ValueError("Original arm geometry implausible")
        if leftward >= 0.15 and upward >= 0.3 and elbow_upward >= 0.12 and row["roadway_occupied"] and row["on_right_turn_route"]:
            runs.append(frame)
    return {
        "frames": 600, "left_arm_upward_frames": runs,
        "left_arm_upward_observed": bool(runs),
        "NRS_484B_420_method_conclusion": None,
        "NRS_484B_769_conclusion": None,
        "original_pixels_verified": False,
    }
