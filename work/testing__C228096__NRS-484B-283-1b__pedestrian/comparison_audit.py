"""Independent fixed-condition checks for curb entry and judgment sampling."""
from __future__ import annotations

from curb_entry import CASES, validate_scene
from delivery_audit import ASSIGNMENT


PAIRS = {
    "walk_vs_run": ("close_walk_into_path", "close_run_into_path", "action"),
    "close_vs_far": ("close_walk_into_path", "far_walk_into_path", "vehicle_gap"),
    "path_vs_road": ("close_walk_into_path", "close_walk_road_only", "route_kind"),
    "path_vs_curb": ("close_walk_into_path", "close_walk_remain_curb", "route_kind"),
    "sweep_sudden_departure_0": ("sudden_departure-0000", "sudden_departure-0001", "departure_hold_s"),
    "sweep_sudden_departure_1": ("sudden_departure-0001", "sudden_departure-0002", "departure_hold_s"),
    "sweep_yield_impossibility_0": ("yield_impossibility-0000", "yield_impossibility-0001", "vehicle_start_gap_m"),
    "sweep_yield_impossibility_1": ("yield_impossibility-0001", "yield_impossibility-0002", "vehicle_start_gap_m"),
}


def audit(comparison_id: str, left_scene: dict, right_scene: dict,
          left_result: dict, right_result: dict) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unassigned curb-entry comparison")
    left_name, right_name, variable = PAIRS[comparison_id]
    cases = [next(item for item in CASES if item.name == name)
             for name in (left_name, right_name)]
    for scene, result, case in ((left_scene, left_result, cases[0]),
                                (right_scene, right_result, cases[1])):
        validate_scene(scene, case)
        if (result.get("format") != "c228096-original-delivery-audit-v1" or
                result.get("source_kind") != "original_native_attempt" or
                result.get("case_id") != ASSIGNMENT + "__" + case.name or
                result.get("frames_checked") != 900 or
                scene.get("action") != case.action or
                scene.get("vehicle_gap") != case.vehicle_gap or
                scene.get("route_kind") != case.route_kind):
            raise ValueError("exact original comparison source missing")
    if (left_result["attempt_id"] == right_result["attempt_id"] or
            left_result["trace_sha256"] == right_result["trace_sha256"]):
        raise ValueError("comparison reuses original motion attempt")
    fixed = ("cell_id", "actor", "pedestrian_person", "vehicle_qualifies",
             "driver_in_control", "road_rect_m", "vehicle_path_rect_m",
             "curb_start_xy", "vehicle_id", "driver_id",
             "pedestrian_identity_source_sha256", "curb_safety_source_sha256",
             "road_boundary_source_sha256", "vehicle_path_source_sha256",
             "driver_control_source_sha256",
             "introductory_exceptions_source_sha256")
    if any(left_scene.get(key) != right_scene.get(key) for key in fixed):
        raise ValueError("fixed curb, driver, path or source differs")
    if (left_scene.get("departure_frame") != right_scene.get("departure_frame")) != (variable == "departure_hold_s"):
        raise ValueError("departure hold comparison variable not isolated")
    for field in ("action", "vehicle_gap", "route_kind"):
        if (left_scene.get(field) != right_scene.get(field)) != (field == variable):
            raise ValueError("declared comparison variable not isolated")
    if variable not in ("vehicle_gap", "vehicle_start_gap_m") and left_scene.get("vehicle_route_xy") != right_scene.get("vehicle_route_xy"):
        raise ValueError("fixed vehicle route differs")
    if variable != "route_kind" and left_scene.get("pedestrian_route_xy") != right_scene.get("pedestrian_route_xy"):
        raise ValueError("fixed pedestrian route differs")
    if variable == "action" and left_scene.get("pedestrian_route_xy") != right_scene.get("pedestrian_route_xy"):
        raise ValueError("walk/run route differs")
    if variable in ("vehicle_gap", "vehicle_start_gap_m") and left_scene.get("vehicle_route_xy") == right_scene.get("vehicle_route_xy"):
        raise ValueError("vehicle-gap construction did not vary")
    if variable == "route_kind" and left_scene.get("pedestrian_route_xy") == right_scene.get("pedestrian_route_xy"):
        raise ValueError("pedestrian route construction did not vary")
    return {"format": "c228096-original-comparison-v1",
            "comparison_id": comparison_id,
            "case_ids": [result["case_id"] for result in (left_result, right_result)],
            "original_attempt_ids": [result["attempt_id"] for result in (left_result, right_result)],
            "compared_variable": variable, "fixed_conditions_checked": list(fixed),
            "requested_difference_isolated": True, "physical_acceptance": False,
            "legal_suddenness_or_impossibility": "unresolved"}
