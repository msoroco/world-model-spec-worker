"""Independent exact comparison of two accepted original rider audits."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from path_observation import ASSIGNMENT


ROUTE_COMPARISONS = {
    name + "_path_vs_roadway": name for name in
    ("bicycle", "electric_bicycle", "electric_scooter")
}


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def compare(left: dict, right: dict, comparison_id: str) -> dict:
    for item in (left, right):
        _require(item.get("format") == "c233829-original-delivery-audit-v1" and
                 item.get("physical_completion") is True and
                 item.get("legal_status") == "unresolved" and
                 item.get("case_id", "").startswith(ASSIGNMENT + "__"),
                 "two original independent delivery audits required")
    _require(left["case_id"] != right["case_id"], "comparison cases must differ")
    for key in ("device_type", "map_id", "roadway_id", "path_id"):
        _require(left[key] == right[key], "comparison fixed condition changed: " + key)
    _require(left["original_frame_count"] == right["original_frame_count"] == 900,
             "comparison camera duration changed")
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        _require(left["camera_decodes"][name] == right["camera_decodes"][name],
                 "comparison camera profile changed: " + name)
    fixed = ("municipal_jurisdiction", "map_geometry", "path_designation",
             "path_adjacency", "sidewalk_absence", "device_classification", "native_adapter")
    for name in fixed:
        _require(left["fixed_sources"][name] == right["fixed_sources"][name],
                 "comparison original source changed: " + name)
    if comparison_id in ROUTE_COMPARISONS:
        device = ROUTE_COMPARISONS[comparison_id]
        _require(left["device_type"] == device and
                 left["target_facility"] == "path" and
                 right["target_facility"] == "roadway" and
                 left["path_usability_context"] == right["path_usability_context"] == "usable",
                 "route comparison exact difference missing")
        for name in ("path_condition", "path_access"):
            _require(left["fixed_sources"][name] == right["fixed_sources"][name],
                     "route comparison path condition changed: " + name)
        _require(left["route_waypoints"] != right["route_waypoints"],
                 "route comparison lacks distinct path and roadway trajectories")
        difference = "original measured path versus roadway rider occupancy"
    elif comparison_id == "path_usability_context":
        _require(left["device_type"] == "electric_scooter" and
                 left["target_facility"] == right["target_facility"] == "roadway" and
                 left["path_usability_context"] == "usable" and
                 right["path_usability_context"] == "unusable",
                 "path condition comparison exact difference missing")
        _require(left["route_waypoints"] == right["route_waypoints"],
                 "path condition comparison route changed")
        _require(any(left["fixed_sources"][name] != right["fixed_sources"][name]
                     for name in ("path_condition", "path_access")),
                 "path condition comparison lacks changed reviewed source")
        difference = "independently reviewed usable versus unusable path context"
    else:
        raise ValueError("unknown exact adjacent-path comparison")
    return {"format": "c233829-original-comparison-audit-v1",
            "comparison_id": comparison_id,
            "case_ids": [left["case_id"], right["case_id"]],
            "observed_difference": difference,
            "original_frame_counts": [900, 900],
            "fixed_source_checks_passed": True,
            "physical_visibility": "requires_independent_review",
            "path_usability_judgment": "requires_independent_review",
            "legal_status": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior original comparison audit")
    left, right = json.loads(args.left.read_text()), json.loads(args.right.read_text())
    args.output.write_text(json.dumps(compare(left, right, args.comparison), indent=2) + "\n")


if __name__ == "__main__":
    main()
