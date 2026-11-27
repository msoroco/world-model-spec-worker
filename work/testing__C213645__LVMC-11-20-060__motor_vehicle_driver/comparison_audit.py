"""Independent fixed-condition and measured-difference driveway comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from driveway_measurement import load_sources, measure


def audit(left_root, right_root, left, right, comparison, *, diagnostic=False):
    if comparison["case_ids"] != [left["case_id"], right["case_id"]]:
        raise ValueError("comparison exact cases differ")
    if not comparison.get("fixed_conditions") or not comparison.get("deliberate_differences"):
        raise ValueError("comparison isolation declaration missing")
    fixed = ("district", "access", "sidewalk", "roadway")
    if any(left["world_setup"][key] != right["world_setup"][key] for key in fixed):
        raise ValueError("comparison fixed district/geometry differs")
    label = comparison["comparison_id"]
    if label == "stop_before_sidewalk":
        allowed = {"entry_behavior", "stop_target"}
        varied = "stop_halt_frame"
    elif label == "pedestrian_precedence":
        allowed = {"pedestrian"}
        varied = "pedestrian_separation_m"
    elif label in ("left_roadway_precedence", "right_roadway_precedence"):
        allowed = {"roadway_vehicle"}
        varied = "roadway_vehicle_separation_m"
    else:
        raise ValueError("unknown exact comparison")
    for section in ("world_setup", "controller"):
        lhs = left[section]
        rhs = right[section]
        for key in set(lhs) | set(rhs):
            if key not in allowed and lhs.get(key) != rhs.get(key):
                raise ValueError("comparison undeclared difference: " + key)
    _, left_source = load_sources(left_root, diagnostic=diagnostic)
    _, right_source = load_sources(right_root, diagnostic=diagnostic)
    geometry_fields = ("map_sha256", "district", "business_district", "access",
                       "road_connection", "driveway_polygon_m", "sidewalk_polygon_m",
                       "roadway_polygon_m", "ego_route_xy_m", "pedestrian_route_xy_m",
                       "roadway_approaches", "district_source", "frontage_source",
                       "private_driveway_source", "sidewalk_source", "roadway_source",
                       "connection_source")
    lg = left_source["driveway_geometry"]
    rg = right_source["driveway_geometry"]
    for key in geometry_fields:
        if lg.get(key) != rg.get(key):
            raise ValueError("comparison original geometry/source differs: " + key)
    left_measure = measure(left_root, left, diagnostic=diagnostic)
    right_measure = measure(right_root, right, diagnostic=diagnostic)
    for measure_name in ("first_sidewalk_frame", "first_roadway_frame"):
        if measure_name not in left_measure or measure_name not in right_measure:
            raise ValueError("comparison original timing source missing")
    return {"format": "worker-driveway-comparison-audit",
            "comparison_id": label, "case_ids": comparison["case_ids"],
            "fixed_conditions_checked": fixed,
            "deliberate_difference_measurement": varied,
            "left": left_measure, "right": right_measure,
            "legal_verdict_claimed": False,
            "physical_comparison_complete": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    rows = [c for c in plan["comparisons"] if c["comparison_id"] == args.comparison]
    if len(rows) != 1:
        raise ValueError("comparison not found")
    row = rows[0]
    by_id = {c["case_id"]: c for c in plan["cases"]}
    print(json.dumps(audit(args.left, args.right, by_id[row["case_ids"][0]],
                           by_id[row["case_ids"][1]], row, diagnostic=args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()
