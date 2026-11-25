"""Author the exact source-bound semantic proposal chain for this assignment."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT.parents[1] / "inputs" / ROOT.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
CELL = ASSIGNMENT["cell"]
ACTOR = ASSIGNMENT["actor"]
LID = ASSIGNMENT["law_id"]
TID = LID + "@" + ACTOR
PROPOSALS = ROOT / "proposals"
PROPOSALS.mkdir(exist_ok=True)


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


quote = LAW["text"]
relevance = {
    "cell_id": CELL["cell_id"], "actor": ACTOR, "status": "draft",
    "relevant_laws": [{"law_id": LID, "quote": quote, "applies_to": [ACTOR],
                       "relevance_type": "direct", "confidence": "high",
                       "notes": "Vehicular traffic facing steady red; requested route crosses surveyed property to the intersecting street."}],
    "borderline_excluded": [],
}
ref_rel = write("relevance.json", relevance)
ref_batch = write("relevance_batch.json", relevance)
phrase = "to avoid the red signal"
note = "Purpose cannot be inferred from trajectory alone; retain separate authored controller declaration and original route evidence."
template = {
    "template_id": TID, "law_id": LID, "actor": ACTOR, "quote": quote,
    "structure": {
        "law_id": LID,
        "activation": {"condition": "Vehicular traffic faces a steady red signal alone.", "numeric_conditions": []},
        "obligation": {"description": "May not proceed on or through any private or public property to enter the intersecting street where traffic is not facing red to avoid the red signal.", "type": "must_not", "numeric_conditions": []},
        "exceptions": [],
        "timing": {"description": "While the signal is steady red alone and the vehicle traverses the property route into the intersecting street.", "numeric_conditions": []},
        "judgment_calls_needed": [{"phrase": phrase, "note": note}],
    },
    "parameter_refs": [{"name": "property_traversal_route", "kind": "controller", "range_or_domain": "road only or surveyed property route"}],
}
ref_template = write("template.json", template)
record = json.loads((ROOT / "construction.json").read_text())["recording_description"]
req = {
    "observables": [{"name": "property_crossing", "unit": "structured", "description": "Original frame body footprints joined to surveyed property and street polygons."}],
    "context_inputs": [
        {"name": "property_survey", "unit": "structured", "description": "Separate surveyed property, lane, signal, and street geometry with source identity."},
        {"name": "controller_purpose", "unit": "structured", "description": "Separately authored route purpose declaration, not inferred from path."},
    ],
    "sweep_dimensions": [], "landmarks": [],
    "recording_needs": [{"name": x["name"], "unit": x["unit"], "description": "Original saved observation for " + x["name"]} for x in record["channels"]],
    "limitations": ["Intent remains a separately sourced declaration; saved movement alone cannot establish purpose.",
                    "Synthetic diagnostic traces do not establish live scene truth or physical authority."],
}
ref_judgment = write("judgment_observables_purpose.json", {"template_id": TID, "phrase": phrase, "note": note,
                                                            "status": "draft", "observable_requirements": req})
binding = {
    "cell_id": CELL["cell_id"], "actor": ACTOR, "status": "draft", "established_contexts": [],
    "law_refs": [{"template_id": TID, "binding_kind": "direct"}], "context_refs": [],
    "fixed_parameters": [],
    "variable_parameters": [{"name": "property_traversal_route", "kind": "controller",
                             "range_or_domain": "road only or surveyed property route", "used_by_laws": [LID]}],
}
ref_binding = write("bindings.json", binding)
cases = json.loads((PROPOSALS / "cases.json").read_text())
cases["cases"] = [case for case in cases["cases"] if not case["case_id"].endswith("__baseline")]
for case in cases["cases"]:
    case["target_type"] = "boundary_probe"
    case["deliberate_differences"] = ["property_traversal_route"]
baseline = {"case_id": ROOT.name + "__baseline", "target_type": "baseline", "target_law_id": LID,
            "variable_assignments": {"property_traversal_route": {"kind": "controller", "value": False}},
            "recording_description": record, "unresolved_judgment_calls": [phrase],
            "rationale": "Shared red-signal and surveyed map setup; road-only route baseline."}
cases["cases"].insert(0, baseline)
cases["status"] = "draft"
cases["sweep_specs"] = [{"sweep_id": "purpose-source-sweep", "target_law_id": LID,
                         "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
                         "missing_inputs": ["Independent evidence of actual driver purpose beyond authored controller intention",
                                            "Live property ownership and signal-facing survey verification"],
                         "rationale": "The two route probes isolate property traversal; this pair does not sweep the purpose judgment or establish live scene truth."}]
ref_cases = write("canonical-cases.json", cases)
write("cases.json", cases)
index = {"format": "worker-semantic-delivery", "assignment_id": ROOT.name,
         "stages": {"relevance_batch": ref_batch, "relevance": ref_rel, "template": ref_template,
                    "judgment_observables": [ref_judgment], "bindings": ref_binding, "cases": ref_cases}}
write("semantic-index.json", index)
print("semantic index", hashlib.sha256((PROPOSALS / "semantic-index.json").read_bytes()).hexdigest())
