"""Independent original-frame comparison for same-direction body ordering."""

import argparse
import hashlib
import json
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
        raise ValueError("unknown exact 267(2)(d) case")
    config = json.loads(required(attempt, "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("comparison attempt selects another case")
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
        raise ValueError("exact body-order comparison absent")
    first, second = [observed(path, cid) for path, cid in zip(attempts, spec["case_ids"])]
    if first[0].suffix != "moving_hold_behind":
        raise ValueError("body-order comparison baseline differs")
    suffix = second[0].suffix
    allowed = {
        "moving_overtake": {"passing_maneuver_request"},
        "moving_abreast": {"passing_maneuver_request"},
        "unit_overtakes_ego": {"passing_maneuver_request", "immediate_approach_request"},
        "preparing_visible_hand_signal": {"unit_state", "visible_preparation_source",
                                          "preparation_cue"},
        "preparing_visible_vehicle_movement": {"unit_state", "visible_preparation_source",
                                                "preparation_cue"},
        "lights_inactive": {"light_request"},
        "lights_unqualified": {"light_request", "front_visible_red_lamp_qualified",
                               "qualifying_lights_source"},
        "officer_directs_otherwise": {"passing_maneuver_request"},
        "regulatory_official_hold_behind": {"emergency_class", "target_vehicle_class",
                                            "authorization_source", "qualifying_lights_source"},
        "no_approach": {"immediate_approach_request"},
    }.get(suffix)
    if allowed is None:
        raise ValueError("unknown body-order contrast")
    for key in set(first[1]) | set(second[1]):
        if key not in allowed and first[1].get(key) != second[1].get(key):
            raise ValueError("emergency comparison fixed site context differs: " + key)
    fa, fb = first[2], second[2]
    if len(fa) != len(fb) or any(
            x["original_frame"] != y["original_frame"] or x["time_s"] != y["time_s"]
            for x, y in zip(fa, fb)):
        raise ValueError("original frame clock differs across comparison")
    change_ego = suffix in {"moving_overtake", "moving_abreast", "unit_overtakes_ego",
                            "officer_directs_otherwise", "no_approach"}
    change_unit = suffix in {"unit_overtakes_ego", "preparing_visible_hand_signal",
                             "preparing_visible_vehicle_movement"}
    if not change_ego and any(
            x["ego_xy"] != y["ego_xy"] or
            x["ego_body_polygon_xy"] != y["ego_body_polygon_xy"] or
            x["ego_brake"] != y["ego_brake"] for x, y in zip(fa, fb)):
        raise ValueError("subject trajectory or body footprint changed outside comparison")
    if not change_unit and any(
            x["emergency_xy"] != y["emergency_xy"] or
            x["emergency_body_polygon_xy"] != y["emergency_body_polygon_xy"]
            for x, y in zip(fa, fb)):
        raise ValueError("target trajectory or body footprint changed outside comparison")
    a, b = first[3], second[3]
    valid = {
        "moving_overtake": b["ego_overtook"] and not a["ego_overtook"],
        "moving_abreast": b["abreast_observed"] and not b["ego_overtook"] and not a["abreast_observed"],
        "unit_overtakes_ego": b["unit_overtook"] and not b["ego_overtook"],
        "preparing_visible_hand_signal": bool(b["visible_hand_signal_original_frames"])
            and not a["visible_hand_signal_original_frames"],
        "preparing_visible_vehicle_movement": bool(
            b["visible_preparation_movement_original_frames"])
            and not b["visible_hand_signal_original_frames"],
        "lights_inactive": any(r["flashing_light_on"] for r in fa)
            and not any(r["flashing_light_on"] for r in fb),
        "lights_unqualified": first[1]["light_request"] == "qualified_active"
            and second[1]["light_request"] == "unqualified_active",
        "officer_directs_otherwise": b["ego_overtook"] and any(r["officer_direction"] for r in fb)
            and not any(r["officer_direction"] for r in fa),
        "regulatory_official_hold_behind": first[1]["target_vehicle_class"] == "authorized_emergency"
            and second[1]["target_vehicle_class"] == "regulatory_official",
        "no_approach": a["subject_approach_observed"] and not b["subject_approach_observed"],
    }[suffix]
    if not valid:
        raise ValueError("body-order contrast absent from original-frame sources: " + suffix)
    if any(row[3]["legal_abreast_overtake_judgment"] != "unresolved"
           for row in (first, second)):
        raise ValueError("comparison invented legal judgment")
    return {"format": "c404479-2d-independent-body-order-comparison-v1",
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
