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
                                     "numeric_conditions": [{"variable": "side_clearance", "operator": "<=", "value": 5, "unit": "feet"}]},
            "obligation": {"type": "must_not", "description": "Do not stop, stand or park at the stated place unless a stated exception applies.",
                "numeric_conditions": []},
            "exceptions": [{"trigger": "necessary traffic conflict", "effect": "exception context to review",
                "replacement_obligation": "follow applicable law", "source_clause": "when necessary to avoid conflict with other traffic in compliance with law"},
                {"trigger": "police officer direction", "effect": "exception context to review",
                 "replacement_obligation": "follow direction", "source_clause": "directions of a police officer"},
                {"trigger": "traffic control device direction", "effect": "exception context to review",
                 "replacement_obligation": "follow direction", "source_clause": "a traffic control device"}],
            "timing": {"description": "During the qualifying stop, stand or park.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": "fixture legal identity and front orientation", "note": "original fixture and street view required"},
                {"phrase": "necessity of traffic conflict in compliance with law", "note": "other actor and lawful necessity require review"},
                {"phrase": "police or device direction", "note": "original authority and direction require review"}]},
        "parameter_refs": []}
    template_ref = write("template.json", template)
    observable_refs = []
    for index, (phrase, note, name) in enumerate((
            ("fixture legal identity and front orientation", "original fixture and street view required", "st.obstruction"),
            ("necessity of traffic conflict in compliance with law", "other actor and lawful necessity require review", "traffic_conflict_context"),
            ("police or device direction", "original authority and direction require review", "police_direction_context"))):
        observable_refs.append(write(f"judgment-{index}.json", {
            "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {"observables": [{"name": name, "unit": "structured", "description": "Original time-joined Native source and reviewed context"}],
                "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": name, "unit": "structured", "description": "Source recording needed for review"}],
                "limitations": ["Original fixture or authority cannot be inferred from a synthetic prop"]}}))
    binding = {"cell_id": "C150668", "actor": "motor_vehicle_driver",
        "status": "draft", "established_contexts": [{"name": "one_way_sidewalk_elevator",
            "source": "frozen cell; original sidewalk elevator/chute and frontage review pending"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "stop_case", "kind": "controller",
            "range_or_domain": "outside or within five-foot side band",
            "used_by_laws": [LAW]}, {"name": "exception_mode", "kind": "world_setup",
            "range_or_domain": "none, traffic conflict, police direction, device direction",
            "used_by_laws": [LAW]}]}
    binding_ref = write("bindings.json", binding)
    selected = json.loads((HERE / "proposals/cases.json").read_text())
    selected["sweep_specs"] = [{"sweep_id": f"c150668-original-review-{index}",
        "target_law_id": LAW, "judgment_refs": [{"phrase": phrase, "note": note}],
        "status": "incomplete", "mode": "one_dimensional", "axes": [],
        "rationale": "Original fixture or authority source is required before a judgment sweep can be frozen.",
        "missing_inputs": ["Original Native source bytes and independent reviewer identity"]}
        for index, (phrase, note) in enumerate((
            ("fixture legal identity and front orientation", "original fixture and street view required"),
            ("necessity of traffic conflict in compliance with law", "other actor and lawful necessity require review"),
            ("police or device direction", "original authority and direction require review")))]
    selected["cases"].insert(0, {"case_id": ASSIGNMENT + "__baseline",
        "target_law_id": LAW, "target_type": "baseline",
        "rationale": "Neutral nonselected comparison anchor",
        "probe": {"primary_variable": "stop_case", "comparison_or_standard": "five-foot side band",
                  "target_value_or_branch": "baseline"},
        "variable_assignments": {"stop_case": {"kind": "controller", "value": "outside"},
                                 "exception_mode": {"kind": "world_setup", "value": "none"}},
        "recording_description": selected["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["original fixture legal identity"]})
    cases_ref = write("canonical-cases.json", selected)
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": rel_batch, "relevance": rel,
                   "template": template_ref, "judgment_observables": observable_refs,
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    print(json.dumps(build()))
