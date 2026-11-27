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
LAW = "NRS-484B-267-2d"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
TEXT = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text(encoding='utf-8'))['law']['text']
JUDGMENTS = (
    ("Upon approaching", "Observe ego-to-unit relative longitudinal distance on original same-direction routes without a numeric legal cutoff.", "relative_approach"),
    ("preparing to move", "Observe a driver-visible hand signal or movement before the ego approach.", "driver_view_movement_cue"),
    ("drive abreast of or overtake", "Observe original-frame longitudinal body overlap and complete behind-to-ahead ordering with actual body extents.", "abreast_overtake_order"),
)
PARAMS = (
    ("unit_class", "world_setup", "authorized emergency or regulatory official", "class"),
    ("light_request", "world_setup", "qualified active, qualified inactive or unqualified active", "class"),
    ("immediate_requested", "controller", "false or true", "boolean"),
    ("passing_maneuver", "controller", "hold_behind, abreast, overtake or unit_overtakes", "class"),
    ("officer_direction_requested", "world_setup", "false or true", "boolean"),
    ("approach_direction", "world_setup", "same_direction", "class"),
    ("unit_state", "world_setup", "moving or preparing", "class"),
    ("preparation_cue", "world_setup", "none, visible hand signal or visible vehicle movement", "class"),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    values = (case.unit_class, case.light_request, case.immediate, case.maneuver,
              case.officer_direction, case.direction, case.state, case.preparation_cue)
    return {name: {"kind": kind, "value": value, "unit": unit}
            for (name, kind, _, unit), value in zip(PARAMS, values)}


def build():
    relevance = {"cell_id": "C404479", "actor": ACTOR, "status": "draft",
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
            "activation": {"condition": "Ego approaches an authorized emergency or regulatory official vehicle moving or visibly preparing to move in the same direction while it uses qualifying flashing lights.",
                           "numeric_conditions": []},
            "obligation": {"description": "The driver of any other vehicle shall not drive abreast of or overtake the moving same-direction target vehicle.", "type": "must_not",
                           "numeric_conditions": []},
            "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                            "description": "Source-bound law-enforcement direction can alter the driver's response."}],
            "timing": {"description": "Observe ego approach, target movement or visible preparation, and body ordering over all original frames.",
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
                "limitations": ["Original approach, body extents and driver-view source review remain required; no new legal cutoff is supplied."]}}))
    binding_ref = write("bindings.json", {"cell_id": "C404479", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                 "unit": unit, "used_by_laws": [LAW]}
                                for name, kind, domain, unit in PARAMS]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared same-direction moving emergency-unit context without a legal finding.",
        "variable_assignments": assignments(CASES[0]),
        "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
        "recording_description": description()}
    cases = [baseline]
    for case in CASES:
        cases.append({"case_id": AID + "__" + case.suffix,
            "target_law_id": LAW, "target_type": "boundary_probe", "status": "draft",
            "rationale": "Exact same-direction approach, longitudinal body order, light use, officer direction or target-class alternative; no legal verdict.",
            "paired_probe_id": "same_direction_abreast_overtake",
            "deliberate_differences": [name for name, _, _, _ in PARAMS],
            "probe": {"primary_variable": "passing_maneuver",
                      "comparison_or_standard": "Compare sealed original approach, lights, body-footprint order and officer context with the clause.",
                      "target_value_or_branch": case.suffix},
            "variable_assignments": assignments(case),
            "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
            "recording_description": description()})
    cases_ref = write("cases.json", {"cell_id": "C404479", "actor": ACTOR,
        "status": "draft", "sweep_specs": [{
            "sweep_id": "abreast_overtake_review", "target_law_id": LAW,
            "judgment_refs": judgments, "status": "incomplete", "mode": "joint",
            "axes": [], "landmarks": [],
            "rationale": "Approach and body-order alternatives are prepared; legal judgment requires original source review.",
            "missing_inputs": ["original approach, body footprints and driver-view camera histories",
                               "independent legal judgment of abreast/overtake context"],
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
