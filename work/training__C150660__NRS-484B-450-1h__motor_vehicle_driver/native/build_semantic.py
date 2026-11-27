"""Source-literal canonical stage proposals for the fixed safety-zone law."""

import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
SOURCE = json.loads((ROOT / "inputs" / FOLDER.name / "assignment.json").read_text())
OUT = FOLDER / "proposals"
OUT.mkdir(exist_ok=True)
LAW = SOURCE["law_id"]
CELL = SOURCE["cell_id"]
ACTOR = SOURCE["actor"]
TEXT = SOURCE["law"]["text"]


def put(name, value):
    path = OUT / (name + ".json")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
             "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                                "applies_to": [ACTOR], "relevance_type": "specific_match",
                                "confidence": "high",
                                "notes": "Exact safety-zone and opposite curb-end stopping restriction."}],
             "borderline_excluded": []}
references = {"relevance_batch": put("relevance_batch", relevance),
              "relevance": put("relevance", relevance)}
params = [
    {"name": "position_request", "kind": "controller",
     "range_or_domain": "between zone and curb, before start, or past end; original footprint independently measured"},
    {"name": "requested_curb_end_gap_ft", "kind": "controller",
     "range_or_domain": "25, 30, 35 or 45 feet requested; actual closest footprint distance measured"},
    {"name": "activity_request", "kind": "controller",
     "range_or_domain": "stop, stand or park attempt; original purpose and state independently reviewed"},
    {"name": "exception_request", "kind": "controller",
     "range_or_domain": "none, traffic conflict, other law, officer direction or device direction"},
    {"name": "observed_zone_and_exception_state", "kind": "subject_behavior",
     "range_or_domain": "original footprint, zone designation, curb and authority source review or unknown"},
]
exceptions = [
    {"trigger": "Necessary to avoid conflict with other traffic",
     "effect": "Exception when necessity is established from original traffic evidence.",
     "replacement_obligation": "Retain original traffic evidence for independent review.",
     "source_clause": "except when necessary to avoid conflict with other traffic"},
    {"trigger": "In compliance with law",
     "effect": "Exception when another law actually governs the activity.",
     "replacement_obligation": "Retain source authority for independent review.",
     "source_clause": "in compliance with law"},
    {"trigger": "Directions of a police officer",
     "effect": "Exception when an actual police direction applies.",
     "replacement_obligation": "Retain original officer direction evidence for review.",
     "source_clause": "the directions of a police officer"},
    {"trigger": "Official traffic-control device",
     "effect": "Exception when an official device direction applies.",
     "replacement_obligation": "Retain original device authority and indication evidence for review.",
     "source_clause": "official traffic-control device"},
]
template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
            "status": "draft", "quote": TEXT,
            "structure": {"law_id": LAW,
                          "activation": {"condition": "A vehicle stops, stands or parks between a safety zone and the adjacent curb or within 30 feet of either opposite curb-end point.",
                                         "numeric_conditions": [{"variable": "footprint distance to either opposite curb-end point",
                                                                 "operator": "<=", "value": 30, "unit": "ft",
                                                                 "source_clause": "within 30 feet of points on the curb immediately opposite the ends of a safety zone"}]},
                          "obligation": {"description": "Do not stop, stand or park in the specified safety-zone area unless a source exception applies.",
                                         "type": "must_not", "numeric_conditions": []},
                          "exceptions": exceptions,
                          "timing": {"description": "Observe the complete stop, stand or park interval and source context.",
                                     "numeric_conditions": []},
                          "judgment_calls_needed": []}, "parameter_refs": params}
references["template"] = put("template", template)
references["judgment_observables"] = []
binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "established_contexts": [],
           "law_refs": [{"template_id": template["template_id"], "binding_kind": "direct"}],
           "context_refs": [], "fixed_parameters": [],
           "variable_parameters": [dict(p, used_by_laws=[LAW]) for p in params]}
references["bindings"] = put("bindings", binding)
references["cases"] = {"path": "proposals/cases.json",
                       "sha256": hashlib.sha256((OUT / "cases.json").read_bytes()).hexdigest()}
put("semantic-index", {"format": "worker-semantic-delivery",
                       "assignment_id": FOLDER.name, "stages": references})
