"""Compare two sealed original cases, checking fixed context and one declared change."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import check_joins, check_source, measure_case, required, rows
from native_packet import AID

HISTORY = "original-curb-position-history.jsonl"
CASE_TO_SITE = {"unit_class": "target_vehicle_class",
                "immediate_request": "immediate_approach_request"}
FRAME_CHANGES = {
    "parallel_request": {"body_yaw_to_edge_deg", "ego_body_vertices_m"},
    "closeness_request": {"edge_distance_m", "ego_xy", "ego_body_vertices_m"},
    "intersection_request": {"intersection_overlap"},
    "subject_position_request": {"position_region", "ego_xy", "ego_body_vertices_m",
                                 "ego_speed_mps", "ego_brake"},
    "light_request": {"flashing_light_on"},
    "immediate_request": {"emergency_xy"},
    "officer_direction_request": {"officer_direction"},
    "approach_direction": {"emergency_xy"},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed(attempt, case):
    attempt = Path(attempt)
    case_id = case["case_id"]
    config = json.loads(required(attempt, "config.json").read_text(encoding="utf-8"))
    if config.get("selected_case_id") != case_id:
        raise ValueError("comparison attempt selects another case")
    diagnostic, sources = check_source(attempt, case_id)
    frames = rows(required(attempt, HISTORY))
    check_joins(attempt, frames)
    site = json.loads(required(attempt, "curb-site.json").read_text(encoding="utf-8"))
    for key, value in case.items():
        if key == "recording_description":
            continue
        if config["case"].get(key) != value:
            raise ValueError("comparison config differs from exact case request: " + key)
    measurements = measure_case(config["case"], site, frames)
    return {"case": case, "frames": frames, "site": site,
            "measurements": measurements, "diagnostic": diagnostic, "sources": sources}


def audit(attempts, comparison_id, plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    spec = next((row for row in plan["comparisons"]
                 if comparison_id == AID + "__" + row["comparison_id"]), None)
    if spec is None or len(attempts) != 2:
        raise ValueError("exact curb/shoulder comparison absent")
    cases = [next(row for row in plan["cases"] if row["case_id"] == cid)
             for cid in spec["case_ids"]]
    first, second = [observed(path, case) for path, case in zip(attempts, cases)]
    changed = set(spec["deliberate_differences"])
    if not changed or not changed <= set(cases[0]):
        raise ValueError("comparison difference declaration is invalid")
    for key in cases[0]:
        if key in changed or key in {"case_id", "variant"}:
            continue
        if key in cases[1] and cases[0][key] != cases[1][key]:
            raise ValueError("comparison fixed case request differs: " + key)
    for key in changed:
        if cases[0][key] == cases[1][key]:
            raise ValueError("declared comparison difference absent: " + key)
        site_key = CASE_TO_SITE.get(key, key)
        if site_key in first["site"] and first["site"][site_key] == second["site"].get(site_key):
            raise ValueError("declared difference absent in source context: " + key)
    allowed_site = changed | {CASE_TO_SITE.get(k, k) for k in changed}
    if "unit_class" in changed:
        allowed_site |= {"emergency_class"}
    if "light_request" in changed:
        allowed_site |= {"front_visible_red_lamp_qualified"}
    if "officer_direction_request" in changed:
        allowed_site |= {"officer_direction_source"}
    if "subject_position_request" in changed:
        allowed_site |= {"yield_response_request"}
    for key in set(first["site"]) | set(second["site"]):
        if key not in allowed_site and first["site"].get(key) != second["site"].get(key):
            raise ValueError("curb comparison fixed site context differs: " + key)
    allowed_frame = set().union(*(FRAME_CHANGES.get(key, set()) for key in changed))
    a, b = first["frames"], second["frames"]
    if len(a) != len(b) or len(a) != 900:
        raise ValueError("comparison original frame count differs")
    for left, right in zip(a, b):
        if left["native_frame"] != right["native_frame"] or left["time_s"] != right["time_s"]:
            raise ValueError("comparison original frame clock differs")
        for key in set(left) | set(right):
            if key in {"frame", "native_frame", "original_frame", "time_s"} or key in allowed_frame:
                continue
            if left.get(key) != right.get(key):
                raise ValueError("curb comparison fixed original sample differs: " + key)
    if any(first["measurements"].get(key) != "unresolved" or
           second["measurements"].get(key) != "unresolved" for key in (
               "immediate_approach_judgment", "parallel_and_as_close_as_possible_judgment",
               "clear_of_intersection_judgment", "signed_shoulder_stop_judgment")):
        raise ValueError("comparison invented legal judgment")
    return {"format": "c183357-1b-independent-curb-comparison-v1",
            "comparison_id": comparison_id, "case_ids": spec["case_ids"],
            "source_hashes": [first["sources"], second["sources"]],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "diagnostic_fixture": first["diagnostic"] and second["diagnostic"],
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
