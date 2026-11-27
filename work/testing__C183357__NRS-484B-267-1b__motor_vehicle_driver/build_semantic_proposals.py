"""Author source-faithful canonical draft stages for emergency-unit movement."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_constructions import description
from native_packet import AID

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))["cases"]
OUT = HERE / "proposals"
LAW = "NRS-484B-267-1b"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
TEXT = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))["law_text"]
JUDGMENTS = (
    ("immediate approach", "Observe original relative routes, positions and motion without a numeric legal cutoff.", "relative_approach"),
    ("parallel to, and as close as possible", "Measure actual body yaw and body-to-right-edge distance, retaining feasibility and legal judgment for review.", "edge_distance"),
    ("clear of any intersection", "Measure original body polygon overlap with the reviewed intersection boundary.", "intersection_overlap"),
    ("paved shoulder signed stopping restriction", "Measure actual stop/traverse state and the reviewed lawful sign's listed class and segment applicability.", "shoulder_region"),
)
PARAMS = (
    ("unit_class", "world_setup", "authorized emergency or regulatory official", "class"),
    ("light_request", "world_setup", "qualified active, qualified inactive or unqualified active", "class"),
    ("immediate_request", "controller", "false or true", "boolean"),
    ("edge_type", "world_setup", "curb or right_edge", "class"),
    ("parallel_request", "controller", "parallel or skewed", "class"),
    ("closeness_request", "controller", "nearest_feasible or intentionally_offset", "class"),
    ("intersection_request", "world_setup", "outside_intersection or inside_intersection", "class"),
    ("subject_position_request", "controller", "roadway, paved_shoulder_stop or paved_shoulder_traverse", "class"),
    ("sign_permitted_class", "world_setup", "none or one of the six listed shoulder-permitted classes", "class"),
    ("officer_direction_request", "world_setup", "none or contrary_direction", "class"),
    ("approach_direction", "world_setup", "opposing or same_direction", "class"),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    return {name: {"kind": kind, "value": case[name], "unit": unit}
            for name, kind, _, unit in PARAMS}


def build():
    relevance = {"cell_id": "C183357", "actor": ACTOR, "status": "draft",
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
            "activation": {"condition": "Immediate approach of an authorized emergency or regulatory official vehicle using qualifying flashing lights.",
                           "numeric_conditions": []},
            "obligation": {"description": "Drive immediately to a parallel position as close as possible to the right edge or applicable curb and clear of any intersection; do not drive to and stop on a signed paved shoulder permitting a listed class.", "type": "must",
                           "numeric_conditions": []},
            "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                            "description": "Source-bound law-enforcement direction can alter the driver's response."}],
            "timing": {"description": "Observe the immediate approach and response over the original 45 seconds.",
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
                "limitations": ["Original approach, body geometry, sign, officer and driver-view review remains required; no new legal cutoff is supplied."]}}))
    binding_ref = write("bindings.json", {"cell_id": "C183357", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                 "unit": unit, "used_by_laws": [LAW]}
                                for name, kind, domain, unit in PARAMS]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared emergency approach and paved shoulder context without a legal finding.",
        "variable_assignments": assignments(CASES[0]),
        "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
        "recording_description": description()}
    cases = [baseline]
    for case in CASES:
        cases.append({"case_id": case["case_id"],
            "target_law_id": LAW, "target_type": "boundary_probe", "status": "draft",
            "rationale": "Exact approach, geometry, sign class, officer direction or statutory alternative; no legal verdict.",
            "paired_probe_id": "emergency_curb_shoulder_position",
            "deliberate_differences": [name for name, _, _, _ in PARAMS],
            "probe": {"primary_variable": "subject_position_request",
                      "comparison_or_standard": "Compare sealed original approach, body geometry, signage, officer context and subject position with the clause.",
                      "target_value_or_branch": case["variant"]},
            "variable_assignments": assignments(case),
            "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
            "recording_description": description()})
    cases_ref = write("cases.json", {"cell_id": "C183357", "actor": ACTOR,
        "status": "draft", "sweep_specs": [{
            "sweep_id": "curb_shoulder_position_review", "target_law_id": LAW,
            "judgment_refs": judgments, "status": "incomplete", "mode": "joint",
            "axes": [], "landmarks": [],
            "rationale": "Approach, curb, intersection and signage alternatives are prepared; positioning judgments require original review.",
            "missing_inputs": ["original approach, body polygon, curb and driver-view camera histories",
                               "independent review of lawful signage and physical feasibility"],
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
