"""Author source-faithful canonical draft stages for emergency-unit movement."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_constructions import description
from emergency_construction import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
LAW = "NRS-484B-267-2f"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
TEXT = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text(encoding='utf-8'))['law']['text']
JUDGMENTS = (
    ("Approaches the driver’s vehicle", "Observe original relative routes, positions and unit motion without a numeric legal cutoff.", "relative_approach"),
    ("preparing to move", "Observe visible hand signals or original unit movement before approach.", "driver_view_movement_cue"),
)
PARAMS = (
    ("unit_class", "world_setup", "authorized emergency or regulatory official", "class"),
    ("light_request", "world_setup", "qualified active, qualified inactive or unqualified active", "class"),
    ("immediate_requested", "controller", "false or true", "boolean"),
    ("yield_requested", "controller", "false or true", "boolean"),
    ("officer_direction_requested", "world_setup", "false or true", "boolean"),
    ("approach_direction", "world_setup", "opposing or same_direction", "class"),
    ("unit_state", "world_setup", "moving, preparing or stopped", "class"),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    values = (case.unit_class, case.light_request, case.immediate, case.yielding,
              case.officer_direction, case.direction, case.state)
    return {name: {"kind": kind, "value": value, "unit": unit}
            for (name, kind, _, unit), value in zip(PARAMS, values)}


def build():
    relevance = {"cell_id": "C405341", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                           "applies_to": [ACTOR], "confidence": "high"}],
        "borderline_excluded": []}
    relevant_ref = write("relevance.json", relevance)
    write("relevance-batch.json", relevance)
    judgments = [{"phrase": phrase, "note": note} for phrase, note, _ in JUDGMENTS]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "status": "draft", "quote": TEXT,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "Ego approaches authorized emergency or regulatory official vehicle moving or visibly preparing to move, using qualifying flashing lights; unit approaches ego for the selected referral.",
                           "numeric_conditions": []},
            "obligation": {"description": "Proceed as required pursuant to subsection 1; unavailable 1a and 1b duties are not inferred.", "type": "must",
                           "numeric_conditions": []},
            "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                            "description": "Source-bound law-enforcement direction can alter the driver's response."}],
            "timing": {"description": "Observe both approach relationships, movement or visible preparation, and response over the original 45 seconds.",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments},
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain,
                            "unit": unit} for name, kind, domain, unit in PARAMS]}
    template_ref = write("template.json", template)
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(JUDGMENTS):
        evidence = {"name": channel, "unit": next(c["unit"] for c in description()["channels"]
                                                if c["name"] == channel), "description": note}
        judgment_refs.append(write("judgment-" + str(index) + ".json", {
            "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {"observables": [evidence], "context_inputs": [],
                "sweep_dimensions": [], "landmarks": [], "recording_needs": [evidence],
                "limitations": ["Original approach, yielding and driver-view source review remains required; no new legal cutoff is supplied."]}}))
    binding_ref = write("bindings.json", {"cell_id": "C405341", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                 "unit": unit, "used_by_laws": [LAW]}
                                for name, kind, domain, unit in PARAMS]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared moving or preparing emergency approach context without a legal finding.",
        "variable_assignments": assignments(CASES[0]),
        "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
        "recording_description": description()}
    cases = [baseline]
    for case in CASES:
        cases.append({"case_id": AID + "__" + case.suffix,
            "target_law_id": LAW, "target_type": "boundary_probe", "status": "draft",
            "rationale": "Exact dual approach, unit state, light use, referred response, officer direction or statutory alternative; no legal verdict.",
            "paired_probe_id": "emergency_approach_and_yield_response",
            "deliberate_differences": [name for name, _, _, _ in PARAMS],
            "probe": {"primary_variable": "yield_requested",
                      "comparison_or_standard": "Compare sealed original approach, flashing lights, officer context and subject response with the clause.",
                      "target_value_or_branch": case.suffix},
            "variable_assignments": assignments(case),
            "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
            "recording_description": description()})
    cases_ref = write("cases.json", {"cell_id": "C405341", "actor": ACTOR,
        "status": "draft", "sweep_specs": [{
            "sweep_id": "right_of_way_review", "target_law_id": LAW,
            "judgment_refs": judgments, "status": "incomplete", "mode": "joint",
            "axes": [], "landmarks": [],
            "rationale": "Approach and yielding alternatives are prepared; right-of-way judgment requires source review.",
            "missing_inputs": ["original approach and driver-view camera histories",
                               "independent legal judgment of yielding"],
            "variable_assignments": assignments(CASES[0]),
            "recording_description": description()}],
        "sweeps_expanded": True, "cases": cases})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": AID, "stages": {
            "relevance_batch": relevant_ref, "relevance": relevant_ref,
            "template": template_ref, "judgment_observables": judgment_refs,
            "bindings": binding_ref, "cases": cases_ref},
        "status": "draft_original_source_pending"})


if __name__ == "__main__":
    build()
