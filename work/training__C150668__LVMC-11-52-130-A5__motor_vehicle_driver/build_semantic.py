"""Draft five semantic stages from the exact supplied LVMC clause."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = "LVMC-11-52-130-A5"
TEMPLATE = LAW + "@motor_vehicle_driver"
QUOTE = ("No person shall stop, stand or park a vehicle except when necessary to avoid "
    "conflict with other traffic in compliance with law or the directions of a police "
    "officer or a traffic control device, in any of the following places: In front of "
    "any sidewalk elevator or chute or within a space of five feet on each side of "
    "such sidewalk elevator or chute.")


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {"cell_id": "C150668", "actor": "motor_vehicle_driver",
        "status": "draft", "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": ["motor_vehicle_driver"], "relevance_type": "specific_match",
            "confidence": "medium", "notes": "Frozen one-way stop/stand sidewalk elevator cell; original fixture and exception sources pending."}],
        "borderline_excluded": []}
    rel = write("relevance.json", relevance)
    rel_batch = write("relevance_batch.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW,
        "actor": "motor_vehicle_driver", "status": "draft", "quote": QUOTE,
        "structure": {"activation": {"condition": "Vehicle stops, stands or parks in front of a sidewalk elevator or chute or within five feet on either side.",
                                     "numeric_conditions": [{"value": 5, "unit": "feet", "relation": "within each side"}]},
            "obligation": {"type": "must_not", "description": "Do not stop, stand or park at the stated place unless a stated exception applies.",
                "numeric_conditions": []},
            "exceptions": ["Necessary to avoid conflict with other traffic in compliance with law",
                           "Directions of a police officer", "Directions of a traffic control device"],
            "timing": {"description": "During the qualifying stop, stand or park.",
                       "numeric_conditions": []},
            "judgment_calls_needed": ["fixture legal identity", "front orientation",
                                      "traffic conflict and direction source"]},
        "parameter_refs": []}
    template_ref = write("template.json", template)
    binding = {"cell_id": "C150668", "actor": "motor_vehicle_driver",
        "status": "draft", "established_contexts": [{"name": "one_way_sidewalk_elevator",
            "source": "frozen cell; original sidewalk elevator/chute and frontage review pending"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "stop_case", "kind": "controller",
            "range_or_domain": "outside or within five-foot side band",
            "used_by_laws": [LAW]}]}
    binding_ref = write("bindings.json", binding)
    selected = json.loads((HERE / "proposals/cases.json").read_text())
    selected["cases"].insert(0, {"case_id": ASSIGNMENT + "__baseline",
        "target_law_id": LAW, "target_type": "baseline",
        "rationale": "Neutral nonselected comparison anchor",
        "probe": {"primary_variable": "stop_case", "comparison_or_standard": "five-foot side band",
                  "target_value_or_branch": "baseline"},
        "variable_assignments": {"stop_case": {"kind": "controller", "value": "outside"}},
        "recording_description": selected["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["original fixture legal identity"]})
    cases_ref = write("canonical-cases.json", selected)
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": rel_batch, "relevance": rel,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    print(json.dumps(build()))
