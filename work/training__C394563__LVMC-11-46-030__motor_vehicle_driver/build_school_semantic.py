"""Draft exact law semantics with unresolved school-lane and release review."""

import hashlib
import json
from pathlib import Path

from school_warning_scene import CASE_VARIANTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = "LVMC-11-46-030"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PHRASES = (
    ("school pedestrian lane", "Original lane authority and nearest side require independent review.", "st.crosswalk"),
    ("giving warning that children are about to cross or are crossing", "Original child context and warning meaning require independent review.", "ru.child"),
    ("signal to go", "Original human gesture or signal meaning requires independent pixel review.", "dev.human_direction"),
    ("not less than fifty feet", "The statute does not specify the vehicle reference point; retain front, centre and rear distances.", "rel.centre_distance"),
)


def write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    variant = json.loads((ROOT / "proposals/variant-cases.json").read_text())
    descriptions = {case["case_id"]: case["recording_description"] for case in variant["cases"]}
    relevance = {"cell_id": "C394563", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
            "relevance_type": "specific_match", "confidence": "medium",
            "notes": "The frozen school-crosswalk travel cell is relevant; school-lane, child warning and municipal authority require original source review."}],
        "borderline_excluded": []}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "status": "draft", "quote": quote,
        "structure": {
            "activation": {"source_clause": "where any signal device, flagman or other person is stationed, giving warning that children are about to cross or are crossing the street",
                           "description": "Observe a stationed warning actor, school pedestrian lane and child-crossing warning context."},
            "obligation": {"type": "must", "source_clause": "to fail to stop not less than fifty feet from the nearest side of a school pedestrian lane",
                           "description": "Retain original front, centre and rear stop distances from the source-surveyed nearest lane side; reserve the legal reference-point judgment."},
            "exceptions": [{"source_clause": "until such signal has stopped, raised, or been removed, or the flagman or person stationed at such pedestrian lane has given a signal to go, or has left the locality",
                            "trigger": "One source-observed statutory release alternative occurs after the stop.",
                            "effect": "Departure may be evaluated against the original release evidence; no legal verdict is assigned.",
                            "replacement_obligation": "Remain stopped until a source-observed release event."}],
            "timing": {"description": "Measure 600 synchronized original frames, cessation under warning, first release and first proceeding."},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _ in PHRASES]},
        "parameter_refs": []}
    variables = [
        {"name": "requested_stop_center_ft", "kind": "controller", "range_or_domain": "40 or 55 feet before nearest lane side", "used_by_laws": [LAW]},
        {"name": "warning_role", "kind": "world_setup", "range_or_domain": "signal_device, flagman or other_person", "used_by_laws": [LAW]},
        {"name": "requested_release_event", "kind": "world_setup", "range_or_domain": "seven exact statutory release alternatives", "used_by_laws": [LAW]},
        {"name": "observed_stop_distance_ft", "kind": "subject_behavior", "range_or_domain": "original Native front, centre and rear feet", "used_by_laws": [LAW]},
    ]
    bindings = {"cell_id": "C394563", "actor": ACTOR, "status": "draft",
        "established_contexts": [], "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [], "variable_parameters": variables}
    def assignments(target, role, release):
        return {"requested_stop_center_ft": {"kind": "controller", "value": target, "unit": "feet"},
                "warning_role": {"kind": "world_setup", "value": role},
                "requested_release_event": {"kind": "world_setup", "value": release},
                "observed_stop_distance_ft": {"kind": "subject_behavior", "value": None, "unit": "feet"}}
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Unselected neutral school-lane context without a claimed warning stop.",
        "variable_assignments": assignments(None, "signal_device", "signal_removed"),
        "recording_description": descriptions[AID + "__probe_1"],
        "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES]}
    cases = [baseline]
    for suffix, (target, role, release) in CASE_VARIANTS.items():
        case_id = AID + "__" + suffix
        cases.append({"case_id": case_id, "target_law_id": LAW,
            "target_type": "boundary_probe", "rationale": "Requested source-reviewed " + role +
                " warning stop and " + release + " release; original conduct and legal status remain open.",
            "variable_assignments": assignments(target, role, release),
            "recording_description": descriptions[case_id],
            "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES],
            "paired_probe_id": "school_warning_source_alternatives",
            "deliberate_differences": ["requested_stop_center_ft", "warning_role", "requested_release_event"],
            "probe": {"primary_variable": "requested_stop_center_ft",
                      "comparison_or_standard": "fifty-foot stop and source-observed release clauses",
                      "target_value_or_branch": str(target) + " ft; " + role + "; " + release}})
    proposal = {"format": "worker-case-proposals", "cell_id": "C394563",
        "actor": ACTOR, "law_id": LAW, "status": "draft", "cases": cases,
        "sweep_specs": [{"sweep_id": AID + "__original_source_review", "target_law_id": LAW,
                         "status": "incomplete",
                         "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note, _ in PHRASES],
                         "rationale": "CPU requests and fixtures preserve unresolved lane, child, signal and vehicle reference evidence.",
                         "missing_inputs": ["Original four-view Native pixels and source-reviewed school pedestrian lane",
                                            "Independent child and warning/release meaning review"]}],
        "sweeps_expanded": True}
    refs = {"relevance_batch": write("relevance-batch.json", relevance),
            "relevance": write("relevance.json", relevance),
            "template": write("template.json", template)}
    judgment = []
    for index, (phrase, note, observable) in enumerate(PHRASES, 1):
        requirement = {"name": observable, "unit": "structured",
                       "description": "Retain the original synchronized source stream for " + observable}
        value = {"template_id": TEMPLATE, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": {
                "observables": [requirement],
                "context_inputs": [{"name": "school_lane_child_warning_review", "unit": "structured",
                                    "description": "Original lane, child, warning and jurisdiction source packet."}],
                "sweep_dimensions": [], "landmarks": [], "recording_needs": [requirement],
                "limitations": ["Synthetic diagnostic sources do not establish legal school-lane, child or warning meaning."]}}
        judgment.append(write("judgment-" + str(index) + ".json", value))
    refs["judgment_observables"] = judgment
    refs["bindings"] = write("bindings.json", bindings)
    refs["cases"] = write("cases.json", proposal)
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "stages": refs})
    return {"selected": len(cases) - 1, "judgments": len(judgment)}


if __name__ == "__main__":
    print(json.dumps(build()))
