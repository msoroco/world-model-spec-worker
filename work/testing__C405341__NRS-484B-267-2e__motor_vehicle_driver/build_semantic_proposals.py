"""Author exact-text canonical draft stages for emergency-unit lane selection."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from build_constructions import description
from emergency_construction import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
LAW = "NRS-484B-267-2e"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
TEXT = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())["law"]["text"]
JUDGMENTS = (
    ("If possible", "Record connected nonadjacent lane route, ego footprint and actual traffic/road/weather circumstances; no legal cutoff.", "nonadjacent_lane_access"),
    ("unsafe or impossible", "Record road geometry, occupied traffic corridor, weather, visibility and surface; leave statutory judgment unresolved.", "traffic_path_occupation"),
    ("any indication that is visible to an approaching driver", "Review original driver-view pixels and movement or hand-signal timing.", "visible_preparation_cue"),
)
PARAMS = (
    ("unit_class", "world_setup", "authorized emergency or regulatory official", "class"),
    ("motion_state", "world_setup", "moving or visible preparation cue", "kind"),
    ("lane_choice_requested", "controller", "adjacent or nonadjacent", "lane"),
    ("condition_kind", "world_setup", "available, roadway, traffic or weather exception context", "kind"),
    ("qualifying_lights_requested", "world_setup", "on or off", "boolean"),
    ("ego_approaching_requested", "controller", "true or false", "boolean"),
    ("officer_direction_requested", "world_setup", "true or false", "boolean"),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    values = (case.unit_class, case.motion_state, case.lane_choice, case.condition,
              case.qualifying_lights, case.approaching, case.officer_direction)
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
            "activation": {"condition": "Approach a qualifying moving or visibly preparing authorized emergency or regulatory official vehicle using qualifying flashing lights.",
                           "numeric_conditions": []},
            "obligation": {"description": "If possible, drive in a lane not adjacent to the target unit lane, subject to stated road, traffic, weather or other unsafe/impossible conditions.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [
                {"source_clause": "except when otherwise directed by a law enforcement officer",
                 "description": "Source-backed officer direction can alter the driver's lane response."},
                {"source_clause": "unless roadway, traffic, weather or other conditions make doing so unsafe or impossible",
                 "description": "Original condition facts needed; statutory safety and possibility remain unresolved."}],
            "timing": {"description": "Observe ego approach, target motion or visible preparation, flashing use and lane trajectory over all original 45 seconds.",
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
                "limitations": ["Original lane network, traffic/weather and driver-view source review remains required; no new legal cutoff is supplied."]}}))
    binding_ref = write("bindings.json", {"cell_id": "C405341", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                 "unit": unit, "used_by_laws": [LAW]}
                                for name, kind, domain, unit in PARAMS]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared emergency lane approach context without a legal finding.",
        "variable_assignments": assignments(CASES[0]),
        "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
        "recording_description": description()}
    cases = [baseline]
    for case in CASES:
        cases.append({"case_id": AID + "__" + case.suffix,
            "target_law_id": LAW, "target_type": "boundary_probe", "status": "draft",
            "rationale": "Exact lane choice, condition, officer direction, activation or statutory alternative; no legal verdict.",
            "paired_probe_id": "emergency_lane_choice_and_context",
            "deliberate_differences": [name for name, _, _, _ in PARAMS],
            "probe": {"primary_variable": "lane_choice_requested",
                      "comparison_or_standard": "Compare original unit lane, ego footprint trajectory and source-backed conditions with the clause.",
                      "target_value_or_branch": case.suffix},
            "variable_assignments": assignments(case),
            "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
            "recording_description": description()})
    cases_ref = write("cases.json", {"cell_id": "C405341", "actor": ACTOR,
        "status": "draft", "sweep_specs": [{
            "sweep_id": "lane_possibility_review", "target_law_id": LAW,
            "judgment_refs": judgments, "status": "incomplete", "mode": "joint",
            "axes": [], "landmarks": [],
            "rationale": "Lane and conditional-context alternatives are prepared; legal possibility and safety require source review.",
            "missing_inputs": ["original lane geometry, traffic and weather histories",
                               "independent legal judgment of possibility and safety"],
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
