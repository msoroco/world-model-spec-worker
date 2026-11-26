"""Author source-faithful NRS 484B.250(4) semantic stage proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_signal as signal


HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
LAW = "NRS-484B-250-4"
CELL = "C24757"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PHRASE = "proceed cautiously"
NOTE = "Cautiousness has no statutory numeric cutoff in this text; retain original movement and blind sightline for review."


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    description = json.loads((HERE / "construction.json").read_text())["recording_description"]
    quote = plan["law_text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
            "relevance_type": "installed uncovered inoperative signal at blind intersection entry",
            "confidence": "medium",
            "notes": "Physical installation, inoperability, sightline and vehicle histories require reviewed original sources."}],
        "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "quote": quote, "structure": {"law_id": LAW,
            "activation": {"condition": "Vehicle enters an intersection controlled by an installed uncovered vehicular signal that is inoperative at entry.",
                           "numeric_conditions": []},
            "obligation": {"description": "Stop at marked stop line, else before near-side crosswalk, else nearest point with view of approaching through-highway traffic; then proceed cautiously yielding to vehicles with prior completed stop or within intersection.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [{"source_clause": "or, if there is none, before entering the crosswalk on the near side",
                            "trigger": "No clearly marked stop line",
                            "effect": "Use near-side crosswalk", "replacement_obligation": "Stop before near-side crosswalk"},
                           {"source_clause": "or, if there is none, at the point nearest the intersection where the driver has a view",
                            "trigger": "No stop line or near-side crosswalk",
                            "effect": "Use nearest-view point", "replacement_obligation": "Stop at source-surveyed nearest-view point"}],
            "timing": {"description": "Measure signal at actual entry, prior stop, other vehicle stop/occupancy and subsequent movement on original frames.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
        "parameter_refs": [{"name": "stop_reference_kind", "kind": "world_setup",
                             "range_or_domain": "marked stop line, near-side crosswalk, nearest-view point"},
                            {"name": "other_vehicle_state", "kind": "world_setup",
                             "range_or_domain": "prior stop, within intersection, neither"},
                            {"name": "ego_entry_policy", "kind": "controller",
                             "range_or_domain": "yield until other clears, or enter before clearance"}]}
    tref = write("template.json", template)
    judgment = {"template_id": TEMPLATE, "phrase": PHRASE,
        "note": NOTE,
        "status": "draft", "observable_requirements": {
            "observables": [{"name": "ego_front_and_cessation", "unit": "structured",
                             "description": "Original 20 Hz post-stop front, speed and movement history."}],
            "context_inputs": [{"name": "reviewed_signal_site", "unit": "source",
                                "description": "Blind sightline and through-highway reviewed context."}],
            "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": "blind_sightline_and_through_highway",
                                 "unit": "structured",
                                 "description": "Reviewed blind approach sightline."}],
            "limitations": ["No legal cautiousness cutoff is supplied by the statute or frozen inputs."]}}
    jref = write("judgment-1.json", judgment)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen blind intersection motor-vehicle cell; physical signal and route sources pending review."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "reviewed_signal_site", "value": "source_packet_pending",
                              "rationale": "Hold source-reviewed blind approach and signal identity across controlled comparisons."}],
        "variable_parameters": [
            {"name": "stop_reference_kind", "kind": "world_setup",
             "range_or_domain": "line, crosswalk, view", "used_by_laws": [LAW]},
            {"name": "other_vehicle_state", "kind": "world_setup",
             "range_or_domain": "prior stop, within, none", "used_by_laws": [LAW]},
            {"name": "ego_entry_policy", "kind": "controller",
             "range_or_domain": "yield or enter", "used_by_laws": [LAW]}]}
    bref = write("bindings.json", binding)
    baseline = {"case_id": signal.ASSIGNMENT + "__baseline",
        "paired_probe_id": "post_stop_vehicle_priority", "rationale": "Shared source-reviewed signal and statutory stop-line reference.",
        "recording_description": description, "target_law_id": LAW,
        "target_type": "baseline", "unresolved_judgment_calls": [PHRASE],
        "variable_assignments": {"stop_reference_kind": {"kind": "world_setup", "value": "stop_line"},
                                 "other_vehicle_state": {"kind": "world_setup", "value": "prior_stop"},
                                 "ego_entry_policy": {"kind": "controller", "value": "yield"}},
        "deliberate_differences": ["other_vehicle_state", "stop_reference_kind", "ego_entry_policy"],
        "probe": {"primary_variable": "other_vehicle_state",
                  "comparison_or_standard": "original prior-stop/within occupancy",
                  "target_value_or_branch": "prior_stop"}}
    cases = [baseline]
    for case in signal.CASES:
        full_id = signal.ASSIGNMENT + "__" + case.name
        differences = ["stop_reference_kind"] if case.reference != "stop_line" else \
            ["other_vehicle_state"] if case.other_state != "prior_stop" else \
            ["ego_entry_policy"]
        cases.append({"case_id": full_id,
            "paired_probe_id": "stop_reference_hierarchy" if case.reference != "stop_line" else
                               "post_stop_vehicle_priority" if case.other_state != "prior_stop" else
                               "yield_entry_order",
            "rationale": "Measure original signal state, statutory stop hierarchy and interacting vehicle without preassigning a legal conclusion.",
            "recording_description": description, "target_law_id": LAW,
            "target_type": "boundary_probe", "unresolved_judgment_calls": [PHRASE],
            "variable_assignments": {
                "stop_reference_kind": {"kind": "world_setup", "value": case.reference},
                "other_vehicle_state": {"kind": "world_setup", "value": case.other_state},
                "ego_entry_policy": {"kind": "controller", "value": case.ego_policy}},
            "deliberate_differences": differences,
            "probe": {"primary_variable": differences[0],
                      "comparison_or_standard": "original entry signal, stop front and vehicle-priority history",
                      "target_value_or_branch": case.name}})
    proposed = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "cases": cases, "sweep_specs": [{
            "sweep_id": "cautious_proceeding_unresolved", "target_law_id": LAW,
            "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
            "status": "incomplete",
            "rationale": "Original trajectory and sightline can be captured, but no source-backed cautiousness sweep range is available.",
            "missing_inputs": ["Reviewed source-grounded cautiousness judgment range and feasibility landmarks."]}],
        "sweeps_expanded": True}
    cref = write("cases.json", proposed)
    index = {"format": "worker-semantic-delivery", "assignment_id": signal.ASSIGNMENT,
        "source": "Exact NRS 484B.250(4) text and frozen C24757 cell",
        "status": "draft", "stages": {"relevance_batch": rel_batch,
            "relevance": rel, "template": tref,
            "judgment_observables": [jref], "bindings": bref, "cases": cref}}
    write("semantic-index.json", index)
    return len(cases) - 1


if __name__ == "__main__":
    print(build())
