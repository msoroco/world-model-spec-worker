"""Author canonical CPU stage proposals for the exact curb-projection law."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / "proposals"
ASSIGNMENT = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text(encoding="utf-8"))
LAW = ASSIGNMENT["law"]
ACTOR = ASSIGNMENT["actor"]
CELL = ASSIGNMENT["cell_id"]
TEMPLATE = LAW["id"] + "@" + ACTOR


def put(name, obj):
    path = PROPOSALS / (name + ".json")
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    PROPOSALS.mkdir(exist_ok=True)
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW["id"], "quote": LAW["text"],
                                    "applies_to": [ACTOR], "relevance_type": "direct curb projection limit",
                                    "confidence": "high", "notes": "Parked motor vehicle at assigned curb."}],
                 "borderline_excluded": []}
    references = {"relevance_batch": put("relevance_batch", relevance),
                  "relevance": put("relevance", relevance)}
    variables = [
        {"name": "requested_projection_m", "kind": "world_setup",
         "range_or_domain": "4.2, 4.572, or 5.0 metres perpendicular to reviewed curb"},
        {"name": "controlling_part", "kind": "world_setup",
         "range_or_domain": "vehicle, attached load, or attached trailer"},
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW["id"], "actor": ACTOR,
                "quote": LAW["text"], "structure": {
                    "law_id": LAW["id"],
                    "activation": {"condition": "Motor vehicle, its load or attached trailer occupies the reviewed curb-side street.",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must_not", "description": LAW["text"],
                                   "numeric_conditions": [{"variable": "requested_projection_m", "operator": ">",
                                                           "value": 4.572, "unit": "m"}]},
                    "exceptions": [],
                    "timing": {"description": "Original 900-frame parked-assembly projection history.", "numeric_conditions": []},
                    "judgment_calls_needed": []},
                "parameter_refs": variables}
    references["template"] = put("template", template)
    references["judgment_observables"] = []
    bindings = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "established_contexts": ["one-way road", "curb-side parking", "motor vehicle driver"],
                "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{**v, "used_by_laws": [LAW["id"]]} for v in variables]}
    references["bindings"] = put("bindings", bindings)
    path = PROPOSALS / "cases.json"
    proposal = json.loads(path.read_text(encoding="utf-8"))
    below = proposal["cases"][0]
    baseline = {**below, "case_id": ROOT.name + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Common reviewed curb and parked-assembly reference."}
    cases = [baseline]
    for item in proposal["cases"]:
        suffix = item["case_id"].rsplit("__", 1)[-1]
        value = item["variable_assignments"]["requested_projection_m"]["value"]
        item["paired_probe_id"] = "projection-boundary" if suffix.startswith("vehicle_") else "projection-" + suffix
        item["deliberate_differences"] = ["requested_projection_m"] if suffix.startswith("vehicle_") else ["controlling_part", "requested_projection_m"]
        item["probe"] = {"primary_variable": "requested_projection_m",
                         "comparison_or_standard": "exact statutory fifteen-foot (4.572 m) perpendicular curb boundary",
                         "target_value_or_branch": suffix,
                         "test_value": value, "unit": "m", "operator": ">"}
        if suffix.startswith("vehicle_"):
            item["target_type"] = "boundary_probe"
            item["probe"]["threshold_ref"] = "obligation.numeric_conditions[0]"
            item["epsilon_used"] = {"value": .428 if suffix != "vehicle_equal" else 0,
                                    "unit": "m", "rationale": "Engineering probe spacing; legal boundary remains exact."}
        else:
            item["target_type"] = "violating_attempt"
        cases.append(item)
    proposal["cases"] = cases
    references["cases"] = put("cases", proposal)
    index = {"format": "worker-semantic-delivery", "assignment_id": ROOT.name,
             "stages": references}
    put("semantic-index", index)


if __name__ == "__main__":
    build()
