"""Independent source-bound comparison of the four right-lane plans.

Only isolation and observed differences are reported. Impediment and passing
necessity remain human review questions on original Native evidence.
"""
from __future__ import annotations

from reviewed_scene import ASSIGNMENT


PAIRS = {
    "extreme_right_position": ("slow_middle_follower", "slow_right_follower"),
    "passing_exception": ("slow_middle_follower", "slow_middle_passing"),
    "immediate_follower_condition": ("slow_middle_follower", "slow_middle_no_immediate_follower"),
}


def _actors(plan):
    return {row["role"]: row for row in plan["actors"]}


def audit(comparison_id: str, left: dict, right: dict,
          left_result: dict, right_result: dict) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unassigned controlled comparison")
    names = PAIRS[comparison_id]
    for plan, result, suffix in ((left, left_result, names[0]),
                                 (right, right_result, names[1])):
        case_id = ASSIGNMENT + "__" + suffix
        if (plan.get("case_id") != case_id or result.get("case_id") != case_id or
                plan.get("format") != "c147344-reviewed-scene-plan-v1" or
                result.get("format") != "c147344-original-follower-relation-join-v1" or
                result.get("original_frame_count") != 900 or
                len(result.get("observations", [])) != 900 or
                not result.get("source", {}).get("trace_sha256") or
                not result.get("source", {}).get("relation_sha256")):
            raise ValueError("exact original comparison case or proof missing")
    if left_result["original_trace_id"] == right_result["original_trace_id"]:
        raise ValueError("comparison reuses one original attempt")
    for key in ("site_sha256", "map_sha256", "cameras", "hz", "frames", "rightmost_lane_id"):
        if left.get(key) != right.get(key):
            raise ValueError("fixed source or capture condition differs: " + key)
    la, ra = _actors(left), _actors(right)
    if set(la) - {"slower_vehicle"} != set(ra) - {"slower_vehicle"}:
        raise ValueError("fixed vehicle roles differ")
    for role in ("ego", "following_vehicle"):
        for field in ("station_m", "target_speed_mps"):
            if la[role][field] != ra[role][field]:
                raise ValueError("fixed actor control differs")
    if comparison_id == "extreme_right_position":
        isolated = (la["ego"]["lane_id"] != ra["ego"]["lane_id"] and
                    la["following_vehicle"]["lane_id"] == la["ego"]["lane_id"] and
                    ra["following_vehicle"]["lane_id"] == ra["ego"]["lane_id"] and
                    "slower_vehicle" not in la and "slower_vehicle" not in ra)
        field = "ego_in_extreme_right_lane"
    elif comparison_id == "passing_exception":
        isolated = (la["ego"]["lane_id"] == ra["ego"]["lane_id"] and
                    la["following_vehicle"]["lane_id"] == ra["following_vehicle"]["lane_id"] and
                    "slower_vehicle" not in la and "slower_vehicle" in ra)
        field = "passing_slower_vehicle_observed"
    else:
        isolated = (la["ego"]["lane_id"] == ra["ego"]["lane_id"] and
                    la["following_vehicle"]["lane_id"] != ra["following_vehicle"]["lane_id"] and
                    "slower_vehicle" not in la and "slower_vehicle" not in ra)
        field = "follower_immediately_behind_in_ego_lane"
    if not isolated:
        raise ValueError("declared comparison variable not isolated")
    left_values = [row.get(field) for row in left_result["observations"]]
    right_values = [row.get(field) for row in right_result["observations"]]
    if any(type(value) is not bool for value in left_values + right_values):
        raise ValueError("original compared observation missing")
    return {"format": "c147344-source-comparison-v1", "comparison_id": comparison_id,
            "case_ids": [left["case_id"], right["case_id"]],
            "fixed_source_sha256": left["site_sha256"],
            "original_trace_ids": [left_result["original_trace_id"], right_result["original_trace_id"]],
            "compared_field": field,
            "observed_true_frames": [sum(left_values), sum(right_values)],
            "comparison_isolated": True, "physical_acceptance": False,
            "legal_impediment_or_exception": "unresolved"}
