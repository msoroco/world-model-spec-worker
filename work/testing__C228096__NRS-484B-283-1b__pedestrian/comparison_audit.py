"""Independent fixed-condition checks for the four curb-entry comparisons."""
from __future__ import annotations

import json
from pathlib import Path

from curb_entry import CASES
from delivery_audit import ASSIGNMENT


PAIRS = {
    "walk_vs_run": ("close_walk_into_path", "close_run_into_path", "action"),
    "close_vs_far": ("close_walk_into_path", "far_walk_into_path", "vehicle_gap"),
    "path_vs_road": ("close_walk_into_path", "close_walk_road_only", "route_kind"),
    "path_vs_curb": ("close_walk_into_path", "close_walk_remain_curb", "route_kind"),
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
             "introductory_exceptions_source_sha256", "departure_frame")
    if any(left_scene.get(key) != right_scene.get(key) for key in fixed):
        raise ValueError("fixed curb, driver, path or source differs")
    for field in ("action", "vehicle_gap", "route_kind"):
        if (left_scene.get(field) != right_scene.get(field)) != (field == variable):
            raise ValueError("declared comparison variable not isolated")
    if variable != "vehicle_gap" and left_scene.get("vehicle_route_xy") != right_scene.get("vehicle_route_xy"):
        raise ValueError("fixed vehicle route differs")
    if variable != "route_kind" and left_scene.get("pedestrian_route_xy") != right_scene.get("pedestrian_route_xy"):
        raise ValueError("fixed pedestrian route differs")
    if variable == "action" and left_scene.get("pedestrian_route_xy") != right_scene.get("pedestrian_route_xy"):
        raise ValueError("walk/run route differs")
    if variable == "vehicle_gap" and left_scene.get("vehicle_route_xy") == right_scene.get("vehicle_route_xy"):
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.receipts.read_text(encoding="utf-8"))
    if set(source) != {"left_audit", "right_audit"}:
        raise ValueError("exact comparison audit receipt paths required")
    root = args.authority_root.resolve()
    site = json.loads((root / "site.json").read_text(encoding="utf-8"))
    left, right, _ = PAIRS[args.comparison]
    results = [json.loads((root / source[key]).read_text(encoding="utf-8"))
               for key in ("left_audit", "right_audit")]
    result = audit(args.comparison, site["scenes"][left], site["scenes"][right], *results)
    if args.output.exists():
        raise ValueError("fresh comparison output required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
