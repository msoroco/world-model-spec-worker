"""Expand the frozen one-way left-turn branch into isolated CPU draft attempts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = "testing__C153046__NRS-484B-307-8c__motor_vehicle_driver"
SOURCE = "inputs/testing__C153046__NRS-484B-307-8c__motor_vehicle_driver/assignment.json"

KINDS = {
    "stopped_leftmost_clear": ("complete_stop", "extreme_left", "one_way_left", "no_conflict"),
    "rolling_leftmost_clear": ("rolling", "extreme_left", "one_way_left", "no_conflict"),
    "stopped_inner_lane_clear": ("complete_stop", "inner_lane", "one_way_left", "no_conflict"),
    "stopped_leftmost_two_way_receive": ("complete_stop", "extreme_left", "two_way", "no_conflict"),
    "stopped_leftmost_pedestrian_yield": ("complete_stop", "extreme_left", "one_way_left", "pedestrian_yield"),
    "stopped_leftmost_pedestrian_advance": ("complete_stop", "extreme_left", "one_way_left", "pedestrian_advance"),
    "stopped_leftmost_traffic_yield": ("complete_stop", "extreme_left", "one_way_left", "traffic_yield"),
    "stopped_leftmost_traffic_advance": ("complete_stop", "extreme_left", "one_way_left", "traffic_advance"),
}

PAIRS = {
    "stop_before_turn": ("stopped_leftmost_clear", "rolling_leftmost_clear", "requested stop"),
    "extreme_left_position": ("stopped_leftmost_clear", "stopped_inner_lane_clear", "approach lane"),
    "receiving_direction": ("stopped_leftmost_clear", "stopped_leftmost_two_way_receive", "receiving road direction"),
    "pedestrian_yield": ("stopped_leftmost_pedestrian_yield", "stopped_leftmost_pedestrian_advance", "requested response to pedestrian"),
    "traffic_yield": ("stopped_leftmost_traffic_yield", "stopped_leftmost_traffic_advance", "requested response to signal-directed traffic"),
}

OBSERVATIONS = {
    "official steady red alone": "source-reviewed signal identity and original per-frame signal state",
    "antecedent stop location": "source-reviewed stop line/crosswalk hierarchy and original front-body position",
    "complete stop": "original speed and stationary interval before entry",
    "extreme left of one-way approach": "source-reviewed approach lane direction and original full-body lane placement",
    "receiving one-way to left": "source-reviewed receiving lane directions and original route entry",
    "pedestrian right-of-way": "original pedestrian body/history and signal-directed movement",
    "other traffic right-of-way": "original other-vehicle body/history and signal-directed movement",
    "yield response": "original ego controls, body path, speed and entry ordering",
}


def build() -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if plan["law_id"] != "NRS-484B-307-8c" or plan["actor"] != "motor_vehicle_driver":
        raise ValueError("frozen case scope differs")
    plan["cases"] = [{
        "case_id": AID + "__" + suffix, "target_law_id": plan["law_id"],
        "target_type": "controlled_attempt", "draft_variables": {
            "stop_request": values[0], "approach_position": values[1],
            "receiving_direction": values[2], "conflict_response_request": values[3],
            "signal_request": "steady_red_alone"},
        "physical_risk_assessment": {"status": "unverified",
            "reason": "Native lane geometry, signal phase and participant route remain unreviewed; no fallback selected."},
        "preparation_status": "controller_cpu_draft_only",
        "physical_acceptance_claimed": False, "legal_judgment": "unresolved",
    } for suffix, values in KINDS.items()]
    plan["comparisons"] = [{
        "comparison_id": name,
        "case_ids": [AID + "__" + left, AID + "__" + right],
        "deliberate_differences": [difference],
        "fixed_conditions": ["motor vehicle driver", "red-alone signal request",
                              "one-way left-turn route except declared difference",
                              "source-reviewed stop/entry boundaries"],
        "status": "draft_requested_only_realized_measurement_pending",
        "realized_difference_claimed": False,
    } for name, (left, right, difference) in PAIRS.items()]
    plan["observations"] = [{"name": name, "source_or_measurement": measurement,
                              "status": "source_review_or_original_capture_pending"}
                             for name, measurement in OBSERVATIONS.items()]
    plan["source_observation_mapping"] = {}
    plan["observation_evidence_mapping"] = [{"term": name, "measurement": measurement,
                                             "source_refs": [SOURCE],
                                             "evidence": "frozen exact law; original site/trace evidence pending"}
                                            for name, measurement in OBSERVATIONS.items()]
    plan["requirement_dispositions"] = [{"requirement": plan["law_id"],
        "source": {"path": SOURCE, "sha256": next(ref["sha256"] for ref in plan["sources"]
                                                   if ref["path"] == SOURCE)},
        "status": "selected_required",
        "case_ids": [case["case_id"] for case in plan["cases"]],
        "evidence_or_gap": "No accepted exact recording; source-reviewed one-way lanes, signal, stop boundary and yielding histories pending."}]
    plan["selected_branch"] = "one_way_left_turn"
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "ego, receiving one-way road, signal and all participants",
             "interval": "approach through full exit"},
            {"view": "approach", "subject": "source-reviewed stop boundary and extreme-left approach lane",
             "interval": "approach through boundary crossing"},
            {"view": "reference_corner", "subject": "pedestrian and signal-directed traffic conflict paths",
             "interval": "first conflict through clearing"},
            {"view": "driver_reference", "subject": "ego-facing signal and turn entry",
             "interval": "approach through receiving-road entry"}],
        "status": "pose and physical pixel coverage require reviewed site and CARLA test"}
    plan["planning_status"] = "eight_isolated_draft_attempts_controller_cpu_tested"
    plan["runtime_uncertainties"] = [
        "Exact Native one-way approach/receiving lane directions, official signal and stop boundary require reviewed sources.",
        "Original pedestrian and signal-directed traffic states, ego stop and realized yield require retained Native histories.",
        "The eight attempted outcomes and five comparisons are requested controls only; construction, semantic and delivery proofs remain unfinished."]
    return plan


if __name__ == "__main__":
    (ROOT / "case-plan.json").write_text(json.dumps(build(), indent=2) + "\n")
    print("eight draft attempts, five isolated comparisons and eight observation mappings")
