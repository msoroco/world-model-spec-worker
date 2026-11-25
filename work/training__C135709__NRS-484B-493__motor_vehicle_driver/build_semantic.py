"""Draft canonical semantic stages from the supplied NRS 484B.493 text."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = "NRS-484B-493"
TEMPLATE = LAW + "@motor_vehicle_driver"
QUOTE = ("When official traffic-control devices are erected giving notice thereof, "
         "a person shall not stand or park a vehicle upon the left-hand side of a one-way street.")


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return path


def ref(path):
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {"cell_id": "C135709", "actor": "motor_vehicle_driver",
        "status": "draft", "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": ["motor_vehicle_driver"], "relevance_type": "specific_match",
            "confidence": "medium", "notes": "Frozen parking restriction device cell; official authority and one-way designation require separate sources."}],
        "borderline_excluded": []}
    rel = ref(write("relevance.json", relevance))
    rel_batch = ref(write("relevance_batch.json", relevance))
    template = {"template_id": TEMPLATE, "law_id": LAW,
        "actor": "motor_vehicle_driver", "status": "draft", "quote": QUOTE,
        "structure": {"activation": {"condition": "Official devices are erected giving notice of the left-side prohibition on a one-way street.",
                                     "numeric_conditions": []},
            "obligation": {"type": "must_not",
                "description": "Stand or park a vehicle upon the left-hand side.",
                "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "At each instant of qualifying standing or parking.",
                                         "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": []}
    template_ref = ref(write("template.json", template))
    binding = {"cell_id": "C135709", "actor": "motor_vehicle_driver",
        "status": "draft", "established_contexts": [{"name": "one_way_signed_narrow_road",
            "source": "frozen narrow-road parking cell; original official sources and physical sign pixels unverified"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "parking_side", "kind": "controller",
            "range_or_domain": "right or left curb request",
            "used_by_laws": [LAW]}]}
    binding_ref = ref(write("bindings.json", binding))
    selected = json.loads((HERE / "proposals/cases.json").read_text())
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": LAW,
        "target_type": "baseline", "rationale": "Neutral nonselected comparison anchor",
        "probe": {"primary_variable": "parking_side",
                  "comparison_or_standard": "sourced one-way street left side",
                  "target_value_or_branch": "baseline"},
        "variable_assignments": {"parking_side": {"kind": "controller", "value": "right"}},
        "recording_description": selected["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["standing versus parking legal purpose"]}
    selected["cases"].insert(0, baseline)
    cases_ref = ref(write("canonical-cases.json", selected))
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": rel_batch, "relevance": rel,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": binding_ref, "cases": cases_ref}}
    index_path = write("semantic-index.json", index)
    print(json.dumps({"semantic_index_sha256": ref(index_path)["sha256"]}))


if __name__ == "__main__":
    build()
