"""Independent source-bound emergency approach/yield comparison audit."""

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path

from analysis import check_source, check_joins, measure_case, required, rows
from emergency_construction import CASES
from native_packet import AID


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed(attempt, case_id):
    attempt = Path(attempt)
    case = next((item for item in CASES if case_id == AID + "__" + item.suffix), None)
    if case is None:
        raise ValueError("unknown exact emergency case")
    config = json.loads(required(attempt, "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("emergency comparison attempt selects another case")
    diagnostic, sources = check_source(attempt, case_id)
    frames = rows(required(attempt, "original-emergency-movement-history.jsonl"))
    check_joins(attempt, frames)
    site = json.loads(required(attempt, "emergency-site.json").read_text())
    measured = measure_case(case, site, frames)
    return case, site, frames, measured, diagnostic, sources


def audit(attempts, comparison_id, plan):
    plan = json.loads(Path(plan).read_text())
    spec = next((row for row in plan["comparisons"]
                 if comparison_id == AID + "__" + row["comparison_id"]), None)
    if spec is None or len(attempts) != 2:
        raise ValueError("exact emergency comparison absent")
    first, second = [observed(path, cid) for path, cid in zip(attempts, spec["case_ids"])]
    if first[0].suffix != "immediate_approach_stop_remain":
        raise ValueError("emergency comparison baseline differs")
    suffix = second[0].suffix
    # Source context is fixed except the one deliberately changed construction field.
    allowed = {"regulatory_official_stop": {"emergency_class", "target_vehicle_class",
                                             "authorization_source", "siren_equipment_source",
                                             "front_visible_red_lamp_source", "qualifying_lights_source"},
               "lights_inactive": {"light_request"},
               "lights_unqualified": {"light_request", "front_visible_red_lamp_qualified",
                                      "front_visible_red_lamp_source", "qualifying_lights_source"},
               "immediate_approach_no_stop": {"stop_response_request"},
               "officer_directs_otherwise": {"stop_response_request", "officer_direction_source"},
               "no_immediate_approach": {"immediate_approach_request", "route_source"},
               "same_direction_approach_stop": {"approach_direction", "route_source"}}.get(suffix, set())
    for key in set(first[1]) | set(second[1]):
        if key not in allowed and first[1].get(key) != second[1].get(key):
            raise ValueError("emergency comparison fixed site context differs: " + key)
    a, b = first[3], second[3]
    fa, fb = first[2], second[2]
    if len(fa) != len(fb) or any(x["original_frame"] != y["original_frame"] or
                                    x["time_s"] != y["time_s"] for x, y in zip(fa, fb)):
        raise ValueError("original frame clock differs across comparison")
    if suffix not in {"no_immediate_approach", "same_direction_approach_stop"} and any(
            x["emergency_xy"] != y["emergency_xy"] for x, y in zip(fa, fb)):
        raise ValueError("unit trajectory changed outside declared comparison")
    if suffix not in {"immediate_approach_no_stop", "officer_directs_otherwise"} and any(
            x["ego_xy"] != y["ego_xy"] or x["ego_brake"] != y["ego_brake"]
            for x, y in zip(fa, fb)):
        raise ValueError("subject trajectory or response changed outside declared comparison")
    if suffix == "immediate_approach_no_stop":
        valid = a["first_brake_original_frame"] is not None and b["first_brake_original_frame"] is None
    elif suffix == "no_immediate_approach":
        valid = b["minimum_early_center_distance_m"] > a["minimum_early_center_distance_m"]
    elif suffix == "lights_inactive":
        valid = any(r["flashing_light_on"] for r in fa) and \
            not any(r["flashing_light_on"] for r in fb)
    elif suffix == "lights_unqualified":
        valid = first[1]["light_request"] == "qualified_active" and \
            second[1]["light_request"] == "unqualified_active"
    elif suffix == "officer_directs_otherwise":
        valid = not any(r["officer_direction"] for r in fa) and \
            any(r["officer_direction"] for r in fb) and \
            a["first_brake_original_frame"] is not None and \
            b["first_brake_original_frame"] is None
    elif suffix == "regulatory_official_stop":
        valid = first[1]["target_vehicle_class"] == "authorized_emergency" and \
            second[1]["target_vehicle_class"] == "regulatory_official"
    elif suffix == "same_direction_approach_stop":
        valid = first[1]["approach_direction"] == "opposing" and \
            second[1]["approach_direction"] == "same_direction" and \
            b["minimum_early_center_distance_m"] < b["initial_center_distance_m"]
    else:
        raise ValueError("unknown emergency contrast")
    if not valid:
        raise ValueError("emergency contrast not present in original-frame sources: " + suffix)
    if any(row[3]["immediate_approach_judgment"] != "unresolved" or
           row[3]["stop_and_remain_judgment"] != "unresolved" for row in (first, second)):
        raise ValueError("comparison invented legal judgment")
    return {"format": "c405341-1c-independent-emergency-comparison-v1",
            "comparison_id": comparison_id, "case_ids": spec["case_ids"],
            "source_hashes": [first[5], second[5]],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "diagnostic_fixture": first[4] and second[4],
            "physical_acceptance": False, "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--attempt", action="append", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing overwrite of independent comparison")
    value = audit(args.attempt, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
