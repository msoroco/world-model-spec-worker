"""Build source-grounded canonical drafts for the emergency approach pair."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
TEMPLATE_ID = LAW["id"] + "@" + ASSIGNMENT["actor"]


def put(name, value):
    path = HERE / "proposals" / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": path.relative_to(HERE).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {"cell_id": ASSIGNMENT["cell_id"], "actor": ASSIGNMENT["actor"],
                 "status": "draft", "relevant_laws": [{
                     "law_id": LAW["id"], "quote": LAW["text"],
                     "applies_to": [ASSIGNMENT["actor"]], "relevance_type": "direct",
                     "confidence": "high", "notes": "The cell has a moving emergency-vehicle approach; visible preparation and officer direction need distinct source review."}],
                 "borderline_excluded": []}
    relevance_batch = put("relevance-batch.json", relevance)
    relevance_cell = put("relevance.json", relevance)
    judgments = [
        {"phrase": "authorized emergency vehicle or an official vehicle of a regulatory agency",
         "note": "Blueprint identity does not prove authorization or agency role."},
        {"phrase": "moving or preparing to move in any direction",
         "note": "Original motion or driver-visible indication must be reviewed; no numeric speed defines preparation."},
        {"phrase": "flashing lights meeting the requirements of subsection 3 of NRS 484A.480",
         "note": "Native lamp readback and original pixels require independent equipment review."},
        {"phrase": "except when otherwise directed by a law enforcement officer",
         "note": "Officer identity, direction, recipient and timing need original sources."},
        {"phrase": "Be prepared to stop",
         "note": "Brake response and stopping distance are engineering observations, not a legal readiness threshold."},
        {"phrase": "visible to an approaching driver",
         "note": "Original camera evidence and actor geometry must establish sight line."},
        {"phrase": "use of hand signals by the driver of the vehicle",
         "note": "A separate source-driver hand signal and its visibility remain to be constructed and reviewed."}]
    parameters = [
        {"name": "ego_stop_preparedness", "kind": "controller",
         "range_or_domain": ["braking_capacity_available", "not_available"]},
        {"name": "responding_vehicle_kind", "kind": "world_setup",
         "range_or_domain": ["authorized_emergency", "regulatory_agency_official"]},
        {"name": "visible_preparation_kind", "kind": "world_setup",
         "range_or_domain": ["already_moving", "visible_movement", "driver_hand_signal"]},
        {"name": "qualifying_flashing_lights", "kind": "world_setup",
         "range_or_domain": [True, False, None]},
        {"name": "officer_direction", "kind": "world_setup",
         "range_or_domain": [True, False, None]}]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW["id"],
                "actor": ASSIGNMENT["actor"], "quote": LAW["text"], "status": "draft",
                "structure": {"law_id": LAW["id"],
                    "activation": {"condition": "Approach to a qualifying moving or visibly preparing emergency or regulatory vehicle using qualifying flashing lights.", "numeric_conditions": []},
                    "obligation": {"description": "Be prepared to stop throughout the approach.", "type": "must", "numeric_conditions": []},
                    "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                                    "description": "An original officer direction may alter the response."}],
                    "timing": {"description": "Observe preparedness continuously during approach without a legal numeric threshold.", "numeric_conditions": []},
                    "judgment_calls_needed": judgments},
                "parameter_refs": parameters}
    template_ref = put("template.json", template)
    observables = ["drv.responding_emergency", "kin.velocity", "sig.lamp",
                   "dev.human_direction", "drv.stopping_distance", "rel.visible",
                   "sig.hand_signal"]
    observed = []
    for i, judgment in enumerate(judgments):
        name = observables[i]
        observed.append(put(f"judgment_observables_{i}.json", {
            "template_id": TEMPLATE_ID, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft",
            "observable_requirements": {
                "observables": [{"name": name, "unit": "structured",
                                 "description": "Frame-joined original motion, source review and camera evidence."}],
                "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "visible_indication", "unit": "structured",
                                     "description": "Four original camera streams and independent indication review."}],
                "limitations": [judgment["note"], "Synthetic fixtures do not prove physical or legal acceptance."]}}))
    bindings = {"cell_id": ASSIGNMENT["cell_id"], "actor": ASSIGNMENT["actor"],
                "status": "draft", "established_contexts": [
                    "Authored moving-source approach; original physical realization remains unverified."],
                "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
                "context_refs": [],
                "fixed_parameters": [{"name": "approach_scene", "value": "same road, source vehicle and camera profile",
                                      "rationale": "The selected response pair changes only the ego brake policy."}],
                "variable_parameters": [dict(p, used_by_laws=[LAW["id"]]) for p in parameters]}
    bindings_ref = put("bindings.json", bindings)
    cases = json.loads((HERE / "proposals/cases.json").read_text())
    description = cases["cases"][0]["recording_description"]
    assignment_values = {
        "ego_stop_preparedness": {"kind": "controller", "value": "braking_capacity_available"},
        "responding_vehicle_kind": {"kind": "world_setup", "value": "authorized_emergency"},
        "visible_preparation_kind": {"kind": "world_setup", "value": "already_moving"},
        "qualifying_flashing_lights": {"kind": "world_setup", "value": None},
        "officer_direction": {"kind": "world_setup", "value": False}}
    baseline = {"case_id": HERE.name + "__shared_baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared semantic comparison reference; no separate capture.",
                "variable_assignments": assignment_values,
                "unresolved_judgment_calls": [j["phrase"] for j in judgments],
                "recording_description": description}
    pair_id = HERE.name + "__moving_response_comparison"
    for case in cases["cases"]:
        choice = case["variable_assignments"]["ego_stop_preparedness"]["value"]
        case["target_type"] = "judgment_sweep"
        case["variable_assignments"] = dict(assignment_values,
            ego_stop_preparedness={"kind": "controller", "value": choice})
        case["paired_probe_id"] = pair_id
        case["deliberate_differences"] = ["ego_stop_preparedness"]
        case["probe"] = {"primary_variable": "ego_stop_preparedness",
                         "comparison_or_standard": "Controlled source-bound engineering response contrast; no legal preparedness cutoff.",
                         "target_value_or_branch": choice}
        case["unresolved_judgment_calls"] = [j["phrase"] for j in judgments]
    cases["cases"].insert(0, baseline)
    cases["sweep_specs"] = [{"sweep_id": HERE.name + "__source_judgments",
        "target_law_id": LAW["id"], "status": "incomplete",
        "judgment_refs": judgments,
        "rationale": "The response pair is built; full physical alternatives and source qualification still require separate cases.",
        "missing_inputs": ["Original vehicle/lamp authority and pixel review; visible preparation, hand signal and officer direction constructions remain pending."]}]
    cases_ref = put("cases.json", cases)
    put("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": HERE.name,
        "stages": {"relevance_batch": relevance_batch, "relevance": relevance_cell,
                   "template": template_ref, "judgment_observables": observed,
                   "bindings": bindings_ref, "cases": cases_ref}})
    print(json.dumps({"judgments": len(judgments), "selected_draft_cases": len(cases["cases"]) - 1}))


if __name__ == "__main__":
    main()
