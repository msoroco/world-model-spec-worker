"""Independent fixed-condition checks for four exact signal/entry probes."""
from __future__ import annotations

from ped_entry import CASES
from delivery_audit import ASSIGNMENT

PAIRS = {
    "entry_vs_wait_none": ("enter_no_other_device", "wait_no_other_device", "movement"),
    "other_device_display_entry": ("enter_no_other_device", "enter_walk_display", "other_device_display"),
    "entry_vs_wait_walk": ("enter_walk_display", "wait_walk_display", "movement"),
}


def audit(comparison_id: str, left_scene: dict, right_scene: dict,
          left_result: dict, right_result: dict) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unassigned pedestrian signal comparison")
    left_name, right_name, variable = PAIRS[comparison_id]
    cases = [next(item for item in CASES if item.case_id == name)
             for name in (left_name, right_name)]
    for scene, result, case in ((left_scene, left_result, cases[0]),
                                (right_scene, right_result, cases[1])):
        if (result.get("format") != "c227824-original-delivery-audit-v1" or
                result.get("source_kind") != "original_native_attempt" or
                result.get("case_id") != ASSIGNMENT + "__" + case.case_id or
                result.get("frames_checked") != 900 or
                scene.get("movement") != case.movement or
                scene.get("other_device_display") != case.other_device_display):
            raise ValueError("exact original signal comparison source missing")
    if (left_result["attempt_id"] == right_result["attempt_id"] or
            left_result["trace_sha256"] == right_result["trace_sha256"]):
        raise ValueError("comparison reuses original motion attempt")
    fixed = ("cell_id", "actor", "jurisdiction", "highway_dedication",
             "public_vehicle_use", "highway_boundary", "person_afoot",
             "facing_orientation", "official_signal", "red_arrow_timing",
             "other_device_inventory", "pedestrian_route",
             "pedestrian_route_xy", "start_signed_boundary_m",
             "official_vehicle_signal", "steady_red", "green_turn_arrow")
    for key in fixed:
        if left_scene.get(key) != right_scene.get(key):
            raise ValueError("fixed highway, signal or route differs: " + key)
    for field in ("movement", "other_device_display"):
        if (left_scene.get(field) != right_scene.get(field)) != (field == variable):
            raise ValueError("declared comparison variable not isolated")
    return {"format": "c227824-original-comparison-v1", "comparison_id": comparison_id,
            "case_ids": [left_result["case_id"], right_result["case_id"]],
            "original_attempt_ids": [left_result["attempt_id"], right_result["attempt_id"]],
            "compared_variable": variable, "fixed_conditions_checked": list(fixed),
            "requested_difference_isolated": True, "physical_acceptance": False,
            "other_device_permission_under_nrs_484b_283": "unresolved"}
