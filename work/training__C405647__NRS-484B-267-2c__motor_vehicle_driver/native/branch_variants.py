"""Distinct Native acquisition requests for source indication and officer review.

These are construction requests, not selected delivery cases. The four requested
paths retain the original road, four cameras, duration and ego response contrast.
"""

from copy import deepcopy
import json
from pathlib import Path

from scene import ASSIGNMENT, request


VARIANTS = ("visible_driver_hand_signal", "officer_directed_otherwise")
RESPONSES = ("braking_capacity_available", "not_available")


def variant_request(variant, response):
    if variant not in VARIANTS or response not in RESPONSES:
        raise ValueError("Unknown exact source indication or response")
    item = deepcopy(request(response))
    item["format"] = "c405647-native-branch-request-v1"
    item["case_id"] = f"{ASSIGNMENT}__{variant}__{response}"
    item["variant"] = variant
    item["source_driver_proxy"] = None
    item["officer_actor"] = None
    if variant == "visible_driver_hand_signal":
        item["emergency_motion_start_frame"] = 240
        item["source_driver_proxy"] = {
            "blueprint": "walker.pedestrian.0001",
            "spawn_xyz_m": [15, -8.25, 1.5],
            "source_vehicle_xyz_m": item["emergency_start_xyz_m"],
            "signal_frames": [150, 199],
            "arm_side": "R",
            "readback": "original_native_bone_pose_and_camera_review_required",
        }
        item["visible_indication"] = "driver_hand_signal_pending_original_review"
    else:
        item["officer_actor"] = {
            "blueprint": "walker.pedestrian.0002",
            "spawn_xyz_m": [-25, -8.25, 1.5],
            "direction_frames": [150, 199],
            "arm_side": "R",
            "requested_direction": "continue_travel",
            "readback": "original_native_bone_pose_and_camera_review_required",
        }
        item["officer_direction"] = "directed_otherwise_pending_original_review"
    item["physical_risk_assessment"]["source_indication"] = (
        "A proxy arm pose is not proof that the source driver or an officer gave a "
        "visible, applicable signal; original actor, identity, pixels and timing need review.")
    return item


def check_pair(variant):
    first, second = (variant_request(variant, name) for name in RESPONSES)
    fixed = set(first) - {"case_id", "requested_setting", "ego_response_policy"}
    if {key: first[key] for key in fixed} != {key: second[key] for key in fixed}:
        raise ValueError("Branch response pair changed a fixed source condition")
    if first["ego_response_policy"] == second["ego_response_policy"]:
        raise ValueError("Branch response contrast absent")
    if variant == "visible_driver_hand_signal":
        if first["source_driver_proxy"]["signal_frames"] != [150, 199]:
            raise ValueError("Source driver hand interval changed")
        if first["emergency_motion_start_frame"] <= 199:
            raise ValueError("Source vehicle must remain stopped through hand signal")
    if variant == "officer_directed_otherwise":
        if first["officer_actor"]["direction_frames"] != [150, 199]:
            raise ValueError("Officer direction interval changed")
    return first, second


def write():
    target = Path(__file__).resolve().parent / "branch-requests"
    target.mkdir(exist_ok=True)
    ids = []
    for variant in VARIANTS:
        for item in check_pair(variant):
            path = target / (variant + "__" + item["requested_setting"] + ".json")
            path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n")
            ids.append(item["case_id"])
    return ids


if __name__ == "__main__":
    print(json.dumps({"draft_case_ids": write(), "selected": False}))
