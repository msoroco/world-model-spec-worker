"""Expand the exact private-way statute into controlled original captures."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCE = {
    "path": "inputs/" + ASSIGNMENT + "/assignment.json",
    "sha256": "7dbf3b04ef6ea6ed60adeed7d0832ce7f579e27a60c99917cb18dd3f4a3ae177",
}
FIXED = [
    "same source-reviewed private-way origin and public-highway connection",
    "same ordinary motor-vehicle driver and 45-second 20 Hz Native episode",
    "same four original synchronized camera streams and site source packet",
    "same vehicle and highway approach lanes, except the declared actor presence",
]
VARIANTS = [
    ("enter_right_wait", "enter", ["right"], "yield_all", "right-approaching highway vehicle; ego waits before connection"),
    ("enter_right_intrude", "enter", ["right"], "continue", "right-approaching highway vehicle; ego enters ahead of its progression"),
    ("enter_left_wait", "enter", ["left"], "yield_all", "left-approaching highway vehicle; ego waits before connection"),
    ("enter_left_intrude", "enter", ["left"], "continue", "left-approaching highway vehicle; ego enters ahead of its progression"),
    ("cross_both_wait", "cross", ["left", "right"], "yield_all", "ego waits before crossing while vehicles approach from both highway directions"),
    ("cross_both_intrude", "cross", ["left", "right"], "continue", "ego crosses ahead of an approaching highway vehicle"),
    ("enter_both_wait", "enter", ["left", "right"], "yield_all", "ego yields to both approaching highway vehicles"),
    ("enter_both_yield_one", "enter", ["left", "right"], "yield_one_only", "ego yields to one approach but enters ahead of the other"),
    ("enter_no_approach", "enter", [], "continue", "no highway vehicle approaches in the reviewed original interval"),
]
COMPARISONS = [
    ("right_wait_vs_intrude", "enter_right_wait", "enter_right_intrude", "ego entry progression relative to same right-approaching vehicle"),
    ("left_wait_vs_intrude", "enter_left_wait", "enter_left_intrude", "ego entry progression relative to same left-approaching vehicle"),
    ("cross_wait_vs_intrude", "cross_both_wait", "cross_both_intrude", "ego crossing progression relative to same two approaches"),
    ("both_wait_vs_yield_one", "enter_both_wait", "enter_both_yield_one", "ego progression relative to second approaching vehicle"),
    ("right_approach_vs_none", "enter_right_intrude", "enter_no_approach", "presence of an approaching highway vehicle; ego entry trajectory held"),
    ("entry_vs_crossing", "enter_both_wait", "cross_both_wait", "entry versus full crossing route; both approaching vehicles and wait policy held"),
]


def main():
    path = ROOT / "case-plan.json"
    plan = json.loads(path.read_text())
    def cid(variant):
        return ASSIGNMENT + "__" + variant
    plan["evidence_review"] = {
        "reviewer": "CPU worker",
        "method": "Reviewed all zero entries in frozen evidence.json, the exact statute, selected cell, source-hashed witness and judgment reference; no accepted original can establish this branch.",
        "facts": [],
        "gaps": [{
            "id": "private-way-original-motion-and-status",
            "requirement": "Private-way ownership and access, public highway status, feasible entry/cross route, every highway approach, and original precedence motion",
            "source": SOURCE,
            "why_existing_insufficient": "Frozen evidence inventory lists no accepted recordings for this assignment.",
        }],
    }
    plan["cases"] = [{
        "case_id": cid(variant),
        "variant": variant,
        "branch": "private-way origin to public highway: " + maneuver,
        "kind": "delivery",
        "planned_original_capture": True,
        "gap_ids": ["private-way-original-motion-and-status"],
        "target_description": description,
        "deliberate_condition": description,
        "draft_variables": {
            "maneuver": maneuver,
            "approach_sides": sides,
            "ego_control_policy": policy,
            "private_way_origin": True,
            "ordinary_motor_driver": True,
        },
        "fixed_conditions": FIXED,
        "candidate_risk": {
            "status": "physical",
            "reason": "The surveyed connection, route and actor arrival timing may not physically realize the intended highway approach; a source-tested spawn/timing fallback is required without changing the comparison variable.",
        },
        "measurement": "original source-sealed highway approach and ego body progression at connection; legal yielding unresolved",
        "legal_status": "pending original physical and independent legal review",
    } for variant, maneuver, sides, policy, description in VARIANTS]
    plan["comparisons"] = [{
        "comparison_id": comparison_id,
        "case_ids": [cid(left), cid(right)],
        "fixed_conditions": FIXED,
        "deliberate_differences": [difference],
        "audit_rule": "Independently compare original source-hashed site packet, all highway actors, ego body paths, frame maps and camera histories; keep legal yielding judgment unresolved.",
    } for comparison_id, left, right, difference in COMPARISONS]
    all_cases = [row["case_id"] for row in plan["cases"]]
    plan["requirement_dispositions"] = [{
        "disposition_index": index,
        "requirement": requirement,
        "status": "selected_required",
        "case_ids": relevant,
        "source": SOURCE,
        "evidence_or_gap": "No accepted original C228096 evidence; selected cases need source-gated Native capture and independent review.",
    } for index, requirement, relevant in [
        (0, "ordinary driver about to enter highway from private way", [cid(v) for v, m, *_ in VARIANTS if m == "enter"]),
        (1, "ordinary driver about to cross highway from private way", [cid(v) for v, m, *_ in VARIANTS if m == "cross"]),
        (2, "yield right-of-way to all vehicles approaching on such highway", all_cases),
        (3, "private origin, public destination and all route/approach context established by original sources", all_cases),
    ]]
    plan["observations"] = [{"name": name, "mandatory": True, "source": source}
                            for name, source in [
        ("private_way_ownership_and_access", "source-hashed ownership/access records and reviewed boundary map"),
        ("public_highway_status_and_boundary", "source-hashed highway dedication/status and boundary map"),
        ("entry_or_crossing_connection", "source-hashed connection map plus original Native ego body route"),
        ("all_highway_vehicle_approaches", "complete 20 Hz actor inventory with route, position, velocity and identity"),
        ("ego_precedence_motion", "original 20 Hz ego body, brake, velocity and conflict-zone histories"),
        ("four_camera_original_pixels", "original four-camera frame maps, PNG hashes and full decoded videos"),
    ]]
    plan["camera_plan"] = {
        "profile": "overview1080-capability",
        "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": view, "interval": "full 45 second original episode", "subject": subject}
            for view, subject in [
                ("overview", "private-way boundary, highway and all approach directions"),
                ("approach", "ego entry/cross route and highway conflict zone"),
                ("reference_corner", "reviewed connection, both highway directions and bodies"),
                ("driver_reference", "original driver, vehicle and view toward approaching highway actors"),
            ]
        ],
    }
    plan["source_observation_mapping"] = []
    plan["planning_status"] = "selected_cpu_construction_in_progress"
    plan["runtime_uncertainties"] = [
        "Original private ownership, public highway designation, routes and actor approach must be reviewed from actual site sources.",
        "Physical realization, full camera coverage, complete actor inventory and legal yielding require later original capture and independent review.",
        "Source-gated site geometry is CPU-tested; Native acquisition/finalization, compatibility, delivery and comparison audits remain construction work.",
    ]
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    print(len(plan["cases"]), len(plan["comparisons"]))


if __name__ == "__main__":
    main()
