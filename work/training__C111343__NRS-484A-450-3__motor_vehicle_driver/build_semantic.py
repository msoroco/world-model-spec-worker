"""Original-law semantic proposals with unresolved conditional safety judgment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
LAW, CELL, ACTOR = (assignment[key] for key in ("law_id", "cell_id", "actor"))
QUOTE = assignment["law"]["text"]
TEMPLATE = LAW + "@" + ACTOR
OUT = HERE / "proposals"


def write(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / (name + ".json")
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {"actor": ACTOR, "cell_id": CELL, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": QUOTE, "applies_to": [ACTOR],
            "relevance_type": "direct", "confidence": "high",
            "notes": "Frozen yield-sign travel cell; safety-stop necessity remains source-dependent."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance-batch", relevance),
            "relevance": write("relevance", relevance)}
    phrase = "if required for safety to stop"
    note = "Whether traffic and sight conditions required a stop is an independent legal judgment, not a time-to-conflict cutoff."
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "quote": QUOTE, "status": "draft",
        "structure": {"activation": {"description": "Driver approaches an intersection governed by a yield sign, and safety requires stopping",
            "source_clause": "The driver of a vehicle approaching a yield sign if required for safety to stop"},
            "obligation": {"description": "Stop before nearest-side crosswalk, else marked stop line, else nearest point with view of intersecting-highway traffic",
                "type": "must", "source_clause": "shall stop before entering the crosswalk on the nearest side of the intersection or, if there is no crosswalk, at a clearly marked stop line, or if none, then at the point nearest the intersecting highway where the driver has a view of approaching traffic"},
            "exceptions": [],
            "timing": {"description": "Conditional need assessed on approach; stopping reference precedes intersection entry"},
            "judgment_calls_needed": [{"phrase": phrase, "note": note}]},
        "parameter_refs": [{"name": "conditional_stop_position", "kind": "controller",
            "range_or_domain": ["before_crosswalk", "past_crosswalk"]}]}
    refs["template"] = write("template", template)
    judgment = {"template_id": TEMPLATE, "phrase": phrase, "note": note,
        "status": "draft", "observable_requirements": {
            "observables": [{"name": "conditional_stop_position", "unit": "m,m/s",
                "description": "Source-body first rest relative to original near-side crosswalk edge across 600 frames."}],
            "context_inputs": [{"name": "safety_context", "unit": "structured",
                "description": "Original intersecting traffic, approach and view evidence; independent judgment required."},
                {"name": "near_side_crosswalk", "unit": "structured",
                 "description": "Original crosswalk geometry and reference hierarchy."}],
            "sweep_dimensions": [{"name": "conditional_stop_position", "unit": "category",
                "description": "Requested front-bumper stopping target; not a safety judgment."}],
            "landmarks": [],
            "recording_needs": [{"name": "conditional_stop_position", "unit": "m,m/s",
                "description": "Frame-joined original body, motion, camera and traffic evidence."}],
            "limitations": ["No legal time-to-conflict threshold is asserted; physical and safety review remain independent."]}}
    refs["judgment_observables"] = [write("judgment_observables_1", judgment)]
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": [{"name": "yield_sign_near_side_crosswalk",
            "source": "frozen yield-sign intersection cell and authored source-readback construction"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "conditional_stop_position", "kind": "controller",
            "range_or_domain": ["before_crosswalk", "past_crosswalk"], "used_by_laws": [LAW]}]}
    refs["bindings"] = write("bindings", binding)
    record = json.loads((HERE / "selected/before_crosswalk/construction.json").read_text())["recording_description"]
    cases = [{"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Unselected neutral yield approach definition.",
        "recording_description": record, "unresolved_judgment_calls": [phrase],
        "variable_assignments": {"conditional_stop_position": {"kind": "controller",
            "unit": "category", "value": "before_crosswalk"}}}]
    for slug in ("before_crosswalk", "past_crosswalk"):
        cases.append({"case_id": AID + "__" + slug, "target_law_id": LAW,
            "target_type": "boundary_probe",
            "probe": {"primary_variable": "conditional_stop_position",
                "comparison_or_standard": "Measured first rest of full front bumper before versus within the present crosswalk, conditional on independent safety finding",
                "target_value_or_branch": slug},
            "paired_probe_id": "C111343-yield-crosswalk-stop-position",
            "deliberate_differences": ["conditional_stop_position"],
            "rationale": "These are physical attempts; safety-stop necessity and legal outcome remain unresolved.",
            "recording_description": record,
            "unresolved_judgment_calls": [phrase],
            "variable_assignments": {"conditional_stop_position": {"kind": "controller",
                "unit": "category", "value": slug}}})
    unresolved = {"sweep_id": "unresolved_safety_stop", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
        "rationale": "The fixed crosswalk-position pair measures stopping geometry; no reviewed physical range or legal time-to-conflict cutoff defines a safety-necessity sweep.",
        "missing_inputs": ["Original Native traffic and sight evidence for independent safety judgment",
                           "Source-backed physical range and spacing for any additional safety-context sweep"]}
    refs["cases"] = write("cases", {"actor": ACTOR, "cell_id": CELL,
        "status": "draft", "sweeps_expanded": True, "cases": cases,
        "semantic_status": "draft", "sweep_specs": [unresolved]})
    index = {"assignment_id": AID, "format": "worker-semantic-delivery", "stages": refs}
    path = OUT / "semantic-index.json"
    path.write_text(json.dumps(index, indent=2, allow_nan=False) + "\n")
    return {"selected_cases": 2, "index_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
