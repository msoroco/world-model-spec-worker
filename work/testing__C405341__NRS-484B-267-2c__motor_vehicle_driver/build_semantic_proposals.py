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
LAW = "NRS-484B-267-2c"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
TEXT = ("Upon approaching an authorized emergency vehicle or an official vehicle of a regulatory agency which is moving or preparing to move in any direction, including, without limitation, arriving at or leaving the scene of a crash or other incident, and making use of flashing lights meeting the requirements of subsection 3 of NRS 484A.480 [DEF-NRS-484A-480-3], the driver of any other vehicle shall, except when otherwise directed by a law enforcement officer: Be prepared to stop. As used in this section, “preparing to move” means any indication that is visible to an approaching driver that an authorized emergency vehicle or an official vehicle of a regulatory agency is about to move, including, without limitation: (a) A movement of the vehicle; or (b) The use of hand signals by the driver of the vehicle.")
JUDGMENTS = (
    ("Be prepared to stop", "Record ego approach, speed, brake and available stopping context; do not infer a legal cutoff or require an actual stop.", "ego_response"),
    ("any indication that is visible to an approaching driver", "Review actual driver-view original pixels and movement or hand signal timing.", "driver_view_movement_cue"),
)
PARAMS = (
    ("unit_class", "world_setup", "authorized emergency or regulatory official", "class"),
    ("cue_kind", "world_setup", "vehicle movement or driver hand signal", "kind"),
    ("cue_visibility_requested", "world_setup", "visible or constructed occluded", "boolean"),
    ("brake_after_cue_requested", "controller", "false or true", "boolean"),
    ("officer_direction_requested", "world_setup", "false or true", "boolean"),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    values = (case.unit_class, case.cue, case.visible, case.brake_after_cue,
              case.officer_direction)
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
            "activation": {"condition": "Approach an authorized emergency or regulatory official vehicle moving or preparing to move, with qualifying flashing lights.",
                           "numeric_conditions": []},
            "obligation": {"description": "Be prepared to stop.", "type": "must",
                           "numeric_conditions": []},
            "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                            "description": "Source-bound law-enforcement direction can alter the driver's response."}],
            "timing": {"description": "Observe the approach, visible movement or hand signal and response over the original 45 seconds.",
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
                "limitations": ["Original movement and driver-view source review remains required; no new legal cutoff is supplied."]}}))
    binding_ref = write("bindings.json", {"cell_id": "C405341", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                 "unit": unit, "used_by_laws": [LAW]}
                                for name, kind, domain, unit in PARAMS]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared emergency approach context without a legal finding.",
        "variable_assignments": assignments(CASES[0]),
        "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
        "recording_description": description()}
    cases = [baseline]
    for case in CASES:
        cases.append({"case_id": AID + "__" + case.suffix,
            "target_law_id": LAW, "target_type": "boundary_probe", "status": "draft",
            "rationale": "Exact movement, visibility, response, officer direction or statutory alternative; no legal verdict.",
            "paired_probe_id": "emergency_movement_and_response",
            "deliberate_differences": [name for name, _, _, _ in PARAMS],
            "probe": {"primary_variable": "cue_visibility_requested",
                      "comparison_or_standard": "Compare sealed original unit motion, driver-view cue and ego response with the clause.",
                      "target_value_or_branch": case.suffix},
            "variable_assignments": assignments(case),
            "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
            "recording_description": description()})
    cases_ref = write("cases.json", {"cell_id": "C405341", "actor": ACTOR,
        "status": "draft", "sweep_specs": [{
            "sweep_id": "preparedness_review", "target_law_id": LAW,
            "judgment_refs": judgments, "status": "incomplete", "mode": "joint",
            "axes": [], "landmarks": [],
            "rationale": "Movement and response alternatives are prepared; preparedness requires source review.",
            "missing_inputs": ["original unit motion and driver-view camera histories",
                               "independent legal judgment of preparedness"],
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
