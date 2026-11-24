"""Build source-faithful draft semantic stages for the seven intersection probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = "LVMC-11-52-130-A11"
TEMPLATE = LAW + "@motor_vehicle_driver"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment_path = ROOT / "inputs" / AID / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = assignment["law"]["text"]
    stages = HERE / "proposals"
    channels = [
        ("original_body_to_intersection_gap", "m", "Original 20 Hz body footprint and source-bound intersection boundary"),
        ("halt_activity", "structured original source record", "Original speed, pose and requested control trace"),
        ("exception_context", "structured original source record", "Original frame-joined traffic and direction observations"),
        ("traffic_conflict_history", "structured original source record", "Original traffic actor trajectories and possible conflicts"),
        ("applicable_law_context", "structured original source record", "Original context for applicable law and observed conduct"),
        ("governing_direction_history", "structured original source record", "Original police or device direction state and facing actor"),
    ]
    description = {
        "channels": [{"name": name, "unit": unit, "method": method,
                      "sampling_rate_hz": 20,
                      "time_window": "Full original 45-second approach and halt episode",
                      "reference_frame": "Original CARLA world frame and 20 Hz frame map",
                      "uncertainty": "Physical capture and legal necessity require later independent review."}
                     for name, unit, method in channels],
        "context_inputs": [{"name": "reviewed_intersection_boundary", "unit": "source record",
                            "method": "Source-hashed loaded OpenDRIVE, reviewed boundary and local route mapping"},
                           {"name": "reviewed_actor_dimensions", "unit": "source record",
                            "method": "Source-hashed selected Native vehicle blueprint and bounding box"}],
        "limitations": ["Requested gap and cause are construction targets, not observed legal outcomes.",
                        "Original pixels, physical motion and necessity remain subject to local independent review."]}
    for row in plan["cases"]:
        if "streams" in row["recording_description"]:
            row["diagnostic_recording_description"] = row["recording_description"]
        row["recording_description"] = description
    (HERE / "case-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    relevance = {
        "cell_id": "C110969", "actor": "motor_vehicle_driver", "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote,
            "applies_to": ["motor_vehicle_driver"],
            "relevance_type": "intersection proximity during destination stopping or standing",
            "confidence": "medium",
            "notes": "Original intersection geometry, halt purpose and exception necessity need independent evidence."}],
        "borderline_excluded": []}
    relevance_ref = write(stages / "relevance.json", relevance)
    write(stages / "relevance_batch.json", relevance)
    judgments = [
        ("necessary to avoid conflict with other traffic", "Original actor trajectories and feasible avoidance alternatives are required; necessity remains unjudged.", "traffic_conflict_history"),
        ("in compliance with law", "Identify applicable law and observed conduct independently of a requested halt.", "applicable_law_context"),
        ("directions of a police officer or a traffic control device", "Retain original governing direction, facing actor and exact halt interval.", "governing_direction_history"),
    ]
    template = {
        "template_id": TEMPLATE, "law_id": LAW, "actor": "motor_vehicle_driver",
        "status": "draft", "quote": quote,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "Vehicle stopping, standing or parking within fifteen feet of an intersection.",
                           "numeric_conditions": [{"variable": "front_body_intersection_gap", "operator": "<", "value": 15, "unit": "ft"}]},
            "obligation": {"description": "Do not stop, stand or park in the stated intersection proximity unless the stated exception applies.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [{"trigger": "necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device",
                            "effect": "The prohibition has an exception only where the applicable necessity and compliance or direction are established.",
                            "replacement_obligation": "Retain original conduct and applicable direction for independent review.",
                            "source_clause": "except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device"}],
            "timing": {"description": "Measure original approach, halt onset and dwell relative to the source-bound intersection boundary and governing context.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments]},
        "parameter_refs": [
            {"name": "front_body_intersection_gap", "kind": "world_setup", "range_or_domain": "requested body-to-boundary gap in feet; observed gap is measured from original source"},
            {"name": "halt_activity", "kind": "controller", "range_or_domain": "destination stop or stand"},
            {"name": "halt_cause", "kind": "world_setup", "range_or_domain": "ordinary destination, observed traffic conflict, police direction or device direction"},
        ]}
    template_ref = write(stages / "template.json", template)
    judgment_refs = []
    for number, (phrase, note, observable) in enumerate(judgments, 1):
        judgment_refs.append(write(stages / f"judgment-{number}.json", {
            "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {
                "observables": [{"name": observable, "unit": "structured original source record",
                                 "description": note}],
                "context_inputs": [{"name": "reviewed_intersection_boundary", "unit": "source record",
                                    "description": "Retain map, route, boundary definition and independent provenance."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": observable, "unit": "structured original source record",
                                     "description": "Keep original frames and source hashes for independent review."}],
                "limitations": ["An authored cause or synthetic fixture is not proof of legal necessity or physical realization."]}}))
    binding = {
        "cell_id": "C110969", "actor": "motor_vehicle_driver", "status": "draft",
        "established_contexts": ["intersection layout", "stop or stand maneuver"],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": ref["name"], "kind": ref["kind"],
                                 "range_or_domain": ref["range_or_domain"], "used_by_laws": [LAW]}
                                for ref in template["parameter_refs"]]}
    binding_ref = write(stages / "bindings.json", binding)
    cases = [{
        "case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared source-bound intersection, actor, route and four-view capture configuration; no acceptance claim.",
        "variable_assignments": {
            "front_body_intersection_gap": {"kind": "world_setup", "value": 16, "unit": "ft"},
            "halt_activity": {"kind": "controller", "value": "stop"},
            "halt_cause": {"kind": "world_setup", "value": "ordinary_destination"}},
        "recording_description": description,
        "unresolved_judgment_calls": [phrase for phrase, _, _ in judgments]}]
    for row in plan["cases"]:
        suffix = row["case_id"].removeprefix(AID + "__")
        is_boundary = suffix in ("stop_14ft", "stop_15ft", "stop_16ft")
        cases.append({
            "case_id": row["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Original source probe of requested intersection gap and stop/stand or exception context; no legal finding.",
            "paired_probe_id": "fifteen_foot_boundary" if is_boundary else "halt_context_at_14ft",
            "deliberate_differences": ["front_body_intersection_gap"] if is_boundary else ["halt_activity", "halt_cause"],
            "variable_assignments": {
                "front_body_intersection_gap": {"kind": "world_setup", "value": row["requested_front_body_gap_ft"], "unit": "ft"},
                "halt_activity": {"kind": "controller", "value": row["activity"]},
                "halt_cause": {"kind": "world_setup", "value": row["halt_cause"]}},
            "unresolved_judgment_calls": [phrase for phrase, _, _ in judgments],
            "recording_description": row["recording_description"],
            "probe": {"primary_variable": "front_body_intersection_gap" if is_boundary else "halt_cause",
                      "comparison_or_standard": "Original source measured gap and frame-linked context; statutory fifteen-foot boundary applies to distance only.",
                      "target_value_or_branch": row["requested_front_body_gap_ft"] if is_boundary else row["halt_cause"],
                      **({"threshold_ref": "activation.numeric_conditions[0]", "operator": "<", "unit": "ft",
                          "test_value": row["requested_front_body_gap_ft"]} if is_boundary else {})},
            **({"epsilon_used": {"value": 1, "unit": "ft", "rationale": "Engineering probe separation around the exact statutory boundary."}} if is_boundary else {})})
    sweeps = [{"sweep_id": f"c110969-judgment-{i}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
               "rationale": "No reviewed physical range or legal surrogate is supplied.",
               "missing_inputs": ["independently reviewed feasible source-bound Native scenario and judgment-range training bounds"]}
              for i, (phrase, note, _) in enumerate(judgments, 1)]
    cases_ref = write(stages / "cases.json", {"cell_id": "C110969", "actor": "motor_vehicle_driver",
                                              "status": "draft", "sweeps_expanded": True,
                                              "cases": cases, "sweep_specs": sweeps})
    write(stages / "semantic-index.json", {
        "format": "worker-semantic-delivery", "assignment_id": AID,
        "source": {"path": str(assignment_path.relative_to(ROOT)),
                   "sha256": hashlib.sha256(assignment_path.read_bytes()).hexdigest()},
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgment_refs,
                   "bindings": binding_ref, "cases": cases_ref},
        "status": "draft_local_source_and_physical_review_pending"})


if __name__ == "__main__":
    main()
