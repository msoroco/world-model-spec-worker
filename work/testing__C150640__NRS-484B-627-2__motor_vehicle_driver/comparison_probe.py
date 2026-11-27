"""Mock original-shaped reports exercise every independent comparison branch."""
from __future__ import annotations

import argparse
import copy
import json

from comparison_audit import PAIRS, audit_pair
from stop_model import ASSIGNMENT


def report(name):
    case_id = ASSIGNMENT + "__" + name
    stop = name != "destination_slow_roll"
    surface = "shoulder" if name == "destination_off_roadway" else "roadway"
    reason = ("safety_conflict" if name == "safety_conflict_stop" else
              "official_direction" if name == "law_direction_stop" else "destination")
    pass_action = name == "destination_follower_passes"
    measurement = {"frame_count": 900, "actual_complete_stop": stop,
                   "stop_surfaces": [surface] if stop else [],
                   "follower_progress_m": 30.0 if pass_action else 6.0,
                   "follower_passed_ego": pass_action,
                   "collision_or_conflict": [None, {"actor_id": 9}] if reason == "safety_conflict" else [None],
                   "official_direction_readback": [None, {"actor_id": 10}] if reason == "official_direction" else [None],
                   "statutory_verdict": None,
                   "normal_reasonable_movement_judgment": None}
    fixed = {key: key + "-same-source" for key in
             ("map", "one_way_direction", "ego_driver", "ego_vehicle",
              "follower_vehicle", "follower_driver", "jurisdiction")}
    comparison = {"source_kind": "original_native_capture",
                  "fixed_source_sha256": fixed,
                  "roadway_source_sha256": "same-roadway-source",
                  "shoulder_source_sha256": "same-shoulder-source",
                  "camera_plan": ["four original cameras"], "duration_s": 45,
                  "stop_purpose_source_sha256": "purpose-" + reason,
                  "conflict_source_sha256": "conflict-" + reason,
                  "direction_source_sha256": "direction-" + reason,
                  "passing_space_source_sha256": "same-passing-space",
                  "measurement": measurement, "requested_surface": surface,
                  "requested_reason": reason,
                  "requested_follower_action": "pass" if pass_action else "follow_and_halt",
                  "requested_complete_stop": stop}
    return {"format": "worker-delivery-audit", "passed": True,
            "protocol_fixture_checked": False, "case_id": case_id,
            "frame_count": 900, "physical_acceptance_claimed": True,
            "comparison_record": comparison}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--mode", choices=("mock_positive", "changed_fixed_source"), required=True)
    args = parser.parse_args()
    pair = PAIRS[args.comparison]
    reports = {ASSIGNMENT + "__" + name: report(name) for name in pair}
    if args.mode == "mock_positive":
        result = audit_pair(args.comparison, reports)
        if not result["physical_comparison_passed"] or result["legal_verdict_claimed"]:
            raise ValueError("mock comparison unexpectedly claimed legal result")
        print(json.dumps({"scope": "synthetic protocol only", "result": result}, indent=2))
        return 0
    changed = copy.deepcopy(reports)
    changed[ASSIGNMENT + "__" + pair[1]]["comparison_record"]["fixed_source_sha256"]["map"] = "different-map"
    try:
        audit_pair(args.comparison, changed)
    except ValueError as error:
        if "changed fixed original stop condition: fixed_source_sha256" not in str(error):
            raise
        print("Expected rejection:", error)
        return 2
    raise ValueError("changed fixed map was accepted")


if __name__ == "__main__":
    raise SystemExit(main())
