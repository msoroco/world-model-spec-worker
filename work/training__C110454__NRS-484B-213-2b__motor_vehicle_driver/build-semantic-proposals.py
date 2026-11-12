"""Build source-bound draft semantic proposals for the selected CPU constructions.

This does not assert Native behavior or alter the frozen assignment. The selected
set includes an authored at-100-foot rail probe; original observations remain pending.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
MANIFEST = json.loads((HERE / "execution-manifest.json").read_text())
LAW = ASSIGNMENT["law_record"]
LAW_ID = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
CELL_ID = ASSIGNMENT["cell_id"]
TEMPLATE_ID = LAW_ID + "@" + ACTOR
PROPOSALS = HERE / "proposals"


def write(name: str, value: dict) -> dict:
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    "cell_id": CELL_ID, "actor": ACTOR, "status": "draft",
    "relevant_laws": [{"law_id": LAW_ID, "quote": LAW["text"],
                       "applies_to": [ACTOR], "relevance_type": "direct",
                       "confidence": "high", "notes": "Exact assigned clause applies to vehicle driving on the left near an intersection or railroad crossing, subject to its one-way exception."}],
    "borderline_excluded": [],
}
template = {
    "template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": ACTOR,
    "quote": LAW["text"], "status": "draft",
    "structure": {
        "law_id": LAW_ID,
        "activation": {"condition": "Vehicle is driven left of highway center while approaching or traversing an intersection or railroad grade crossing on a highway that is not one-way.",
                       "numeric_conditions": [{"variable": "observed_left_side_closest_distance_ft", "operator": "<=", "value": 100, "unit": "ft"}]},
        "obligation": {"type": "must_not", "description": "Do not drive to the left side of the highway in the stated zone."},
        "exceptions": [{"source_clause": "Subsection 2 does not apply upon a one-way highway.",
                        "description": "The subsection is inapplicable on a one-way highway."}],
        "timing": {"description": "At any time while within 100 feet of approach or while traversing either named feature.", "numeric_conditions": []},
        "judgment_calls_needed": [],
    },
    "parameter_refs": [
        {"name": "crossing_kind", "kind": "world_setup", "range_or_domain": ["intersection", "railroad_grade_crossing"]},
        {"name": "one_way_designation", "kind": "world_setup", "range_or_domain": [False, True]},
        {"name": "commanded_left_side_route", "kind": "controller", "range_or_domain": [False, True]},
        {"name": "commanded_left_side_closest_distance_ft", "kind": "controller", "range_or_domain": "nonnegative minimum feet across the left-side interval; must be checked against Native geometry"},
        {"name": "observed_left_side_closest_distance_ft", "kind": "subject_behavior", "range_or_domain": "Native minimum body distance in feet while left of center, initially unknown"},
        {"name": "observed_left_side_occupancy", "kind": "subject_behavior", "range_or_domain": [False, True, None]},
    ],
}
binding = {
    "cell_id": CELL_ID, "actor": ACTOR, "status": "draft",
    "established_contexts": ["Authored intersection and railroad crossing candidates; all Native map and body observations require original capture."],
    "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
    "context_refs": [], "fixed_parameters": [],
    "variable_parameters": [dict(parameter, used_by_laws=[LAW_ID]) for parameter in template["parameter_refs"]],
}


def assignment(kind: str, value, unit: str) -> dict:
    return {"kind": kind, "value": value, "unit": unit}


def assignments(crossing: str, one_way: bool, left: bool, distance: float) -> dict:
    return {
        "crossing_kind": assignment("world_setup", crossing, "categorical"),
        "one_way_designation": assignment("world_setup", one_way, "boolean"),
        "commanded_left_side_route": assignment("controller", left, "boolean"),
        "commanded_left_side_closest_distance_ft": assignment("controller", distance, "ft"),
        "observed_left_side_closest_distance_ft": assignment("subject_behavior", None, "ft"),
        "observed_left_side_occupancy": assignment("subject_behavior", None, "boolean"),
    }


# The construction's sampled full-body geometry reports nearest front distances
# of 46.1 m and 16.1 m for these broad rail windows. They are not 99/100/101-foot probes.
specs = {
    "rail_reference": ("railroad_grade_crossing", False, True, 151.25, "rail_distance", "commanded_left_side_closest_distance_ft"),
    "rail_contrast": ("railroad_grade_crossing", False, True, 52.82, "rail_distance", "commanded_left_side_closest_distance_ft"),
    "rail_at": ("railroad_grade_crossing", False, True, 100.0, "rail_distance", "commanded_left_side_closest_distance_ft"),
    "oneway_absent": ("intersection", False, True, 6.89, "oneway_exception", "one_way_designation"),
    "oneway_present": ("intersection", True, True, 6.89, "oneway_exception", "one_way_designation"),
    "traversal_reference": ("intersection", False, False, 0.0, "traversal_route", "commanded_left_side_route"),
    "traversal_contrast": ("intersection", False, True, 0.0, "traversal_route", "commanded_left_side_route"),
}
entries = MANIFEST["cases"]
assert {entry["case_id"].split("__")[-1] for entry in entries} == set(specs)
first_description = json.loads((HERE / entries[0]["construction"]).read_text())["recording_description"]
cases = [{
    "case_id": HERE.name + "__semantic_baseline", "target_law_id": None,
    "target_type": "baseline", "rationale": "Neutral right-side route, unselected and not an asserted Native recording.",
    "variable_assignments": assignments("intersection", False, False, 0.0),
    "unresolved_judgment_calls": [], "recording_description": deepcopy(first_description),
}]
for entry in entries:
    suffix = entry["case_id"].split("__")[-1]
    crossing, one_way, left, distance, group, variable = specs[suffix]
    description = json.loads((HERE / entry["construction"]).read_text())["recording_description"]
    cases.append({
        "case_id": entry["case_id"], "target_law_id": LAW_ID,
        "target_type": "boundary_probe" if group == "rail_distance" else "violating_attempt" if suffix.endswith("contrast") or suffix == "oneway_absent" else "compliant_attempt",
        "rationale": "Selected authored setting; observed distance, lane designation and left-side occupancy remain unverified until Native capture.",
        "variable_assignments": assignments(crossing, one_way, left, distance),
        "unresolved_judgment_calls": [], "recording_description": description,
        "paired_probe_id": group, "deliberate_differences": [variable],
        "probe": {"primary_variable": variable,
                  "comparison_or_standard": "paired authored setting against exact statutory clause",
                  "target_value_or_branch": distance if group == "rail_distance" else one_way if group == "oneway_exception" else left,
                  **({"threshold_ref": "activation.numeric_conditions[0]", "operator": "<=", "unit": "ft", "test_value": distance} if group == "rail_distance" else {})},
        **({"epsilon_used": "authored below, at and above 100 feet"} if group == "rail_distance" else {}),
    })
case_stage = {"cell_id": CELL_ID, "actor": ACTOR, "status": "draft", "cases": cases, "sweep_specs": []}
index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
         "status": "draft_seven_case_threshold_coverage", "stages": {
             "relevance_batch": write("relevance-batch.json", relevance),
             "relevance": write("relevance.json", relevance),
             "template": write("template.json", template),
             "judgment_observables": [],
             "bindings": write("bindings.json", binding),
             "cases": write("canonical-cases.json", case_stage),
         }}
write("semantic-index.json", index)
print("Wrote draft source-bound semantic chain with", len(cases) - 1, "selected cases")
