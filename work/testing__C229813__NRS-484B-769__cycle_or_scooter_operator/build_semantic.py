"""Draft canonical stages for the assigned right-arm alternative only."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ASSIGNMENT = ROOT.name
LAW = "NRS-484B-769"
ACTOR = "cycle_or_scooter_operator"
QUOTE = PLAN["law_text"]
DESCRIPTION = json.loads((ROOT / "config.json").read_text())["case"]["recording_description"]
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(kind, posture):
    return {
        "cycle_kind": {"kind": "world_setup", "value": kind, "unit": "category"},
        "right_arm_pose_request": {"kind": "controller", "value": posture,
                                   "unit": "category"},
        "original_right_arm_pose": {"kind": "subject_behavior", "value": None,
                                    "unit": "m"}}


def main():
    relevance = write("relevance.json", {
        "cell_id": "C229813", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW,
                           "quote": "except that the operator may give a signal for a right turn by extending his or her right hand and arm horizontally and to the right side of the bicycle, electric bicycle or electric scooter.",
                           "applies_to": [ACTOR], "relevance_type": "specific_match",
                           "confidence": "medium", "notes": "Conditional on sourced covered operator, roadway, right turn and actual rider-arm event."}],
        "borderline_excluded": []})
    template = write("template.json", {
        "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "status": "draft",
        "quote": QUOTE,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "Covered bicycle/electric bicycle/electric scooter operator on a roadway gives a hand-and-arm signal.",
                           "numeric_conditions": []},
            "obligation": {"description": "Give signals by hand and arm in the referenced manner; this package probes only the stated alternative right-turn form.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [{"trigger": "covered operator gives a right-turn signal",
                            "effect": "alternative form permitted",
                            "replacement_obligation": "right hand and arm extended horizontally to the operator's right side",
                            "source_clause": "except that the operator may give a signal for a right turn by extending his or her right hand and arm horizontally and to the right side of the bicycle, electric bicycle or electric scooter."}],
            "timing": {"description": "Measure actual original signal event during reviewed right-turn route; no independent deadline inferred.",
                       "numeric_conditions": []},
            "judgment_calls_needed": []},
        "parameter_refs": [
            {"name": "cycle_kind", "kind": "world_setup", "range_or_domain": "bicycle, electric_bicycle, electric_scooter", "unit": "category"},
            {"name": "right_arm_pose_request", "kind": "controller", "range_or_domain": "horizontal_right_arm, downward_right_arm, bent_right_arm", "unit": "category"},
            {"name": "original_right_arm_pose", "kind": "subject_behavior", "range_or_domain": "original shoulder/elbow/wrist projections", "unit": "m"}]})
    bindings = write("bindings.json", {
        "cell_id": "C229813", "actor": ACTOR, "status": "draft",
        "established_contexts": [],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "right_turn_route", "value": "source_reviewed",
                              "rationale": "Fixed right-turn maneuver and roadway across each kind's posture comparison."}],
        "variable_parameters": [
            {"name": "cycle_kind", "kind": "world_setup", "range_or_domain": "three covered kinds", "used_by_laws": [LAW], "unit": "category"},
            {"name": "right_arm_pose_request", "kind": "controller", "range_or_domain": "three physical requests", "used_by_laws": [LAW], "unit": "category"},
            {"name": "original_right_arm_pose", "kind": "subject_behavior", "range_or_domain": "actual 20 Hz joint readback", "used_by_laws": [LAW], "unit": "m"}]})
    cases = [{"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared reviewed right-turn route and source gate without a legal verdict.",
              "variable_assignments": assignment("bicycle", "horizontal_right_arm"),
              "unresolved_judgment_calls": [], "recording_description": DESCRIPTION}]
    for planned in PLAN["cases"]:
        case_id = planned["case_id"]
        kind = planned["operator_vehicle_kind"]
        posture = case_id[len(ASSIGNMENT) + len(kind) + 3:]
        cases.append({
            "case_id": case_id, "target_law_id": LAW,
            "target_type": "compliant_attempt" if posture == "horizontal_right_arm" else "violating_attempt",
            "rationale": "Requested alternative-form posture contrast only; actual form and any legal result remain unconfirmed until original review.",
            "variable_assignments": assignment(kind, posture),
            "unresolved_judgment_calls": [],
            "paired_probe_id": kind + "_signal_posture",
            "deliberate_differences": ["right_arm_pose_request"],
            "probe": {"primary_variable": "right_arm_pose_request",
                      "comparison_or_standard": "right-side horizontal statutory alternative versus other right-arm requests",
                      "target_value_or_branch": posture},
            "recording_description": DESCRIPTION})
    cases_ref = write("cases.json", {"cell_id": "C229813", "actor": ACTOR,
                                     "status": "draft", "cases": cases,
                                     "sweep_specs": []})
    write("semantic-index.json", {
        "format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
        "status": "draft_original_physical_review_pending",
        "stages": {"relevance_batch": relevance, "relevance": relevance,
                   "template": template, "judgment_observables": [],
                   "bindings": bindings, "cases": cases_ref}})
    print(json.dumps({"semantic_cases": len(cases), "selected": len(cases) - 1}))


if __name__ == "__main__":
    main()
