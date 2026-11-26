"""Author source-grounded canonical stage proposals for exact parking cases."""

import hashlib
import json
from pathlib import Path

from author_bundles import RECORDING
from comparison_audit import CASES
from parking_place import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / "proposals"
LAW = "NRS-484B-500"
ACTOR = "vehicle_parker"
TEXT = "When official traffic-control devices are erected at hazardous or congested places, a person shall not stop, stand or park a vehicle in any such designated place."
PARAMETERS = (
    ("requested_footprint", "world_setup", "inside or wholly outside source-designated place"),
    ("requested_conduct", "controller", "stop, stand or park scenario intention and control"),
    ("place_context_for_review", "world_setup", "hazardous or congested physical facts for review"),
)


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def author():
    PROPOSALS.mkdir(exist_ok=True)
    relevance = {"cell_id": "C229439", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT, "applies_to": [ACTOR],
                                    "relevance_type": "direct parking restriction at designated place",
                                    "confidence": "high",
                                    "notes": "Official device and hazardous/congested place remain original-source review questions."}],
                 "borderline_excluded": []}
    write(PROPOSALS / "relevance_batch.json", relevance)
    write(PROPOSALS / "relevance.json", relevance)
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "quote": TEXT,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "Erected official traffic-control device designates a place at a hazardous or congested location.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Person shall not stop, stand or park a vehicle in any such designated place.",
                                   "type": "must_not", "numeric_conditions": []},
                    "exceptions": [],
                    "timing": {"description": "Observe approach, halt and final stationary position in original frames.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": []},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in PARAMETERS]}
    write(PROPOSALS / "template.json", template)
    binding = {"cell_id": "C229439", "actor": ACTOR, "status": "draft",
               "established_contexts": ["road", "park maneuver", "parking restriction device"],
               "law_refs": [{"template_id": LAW + "@" + ACTOR, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain, "used_by_laws": [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    write(PROPOSALS / "bindings.json", binding)
    cases = {"cell_id": "C229439", "actor": ACTOR, "status": "draft",
             "cases": [], "sweep_specs": []}
    def assignments(conduct, footprint, context):
        values = dict(requested_conduct=conduct, requested_footprint=footprint,
                      place_context_for_review=context)
        return {name: {"kind": kind, "value": values[name],
                       "note": "Authored intent and context; actual physical/legal status remains unconfirmed"}
                for name, kind, _ in PARAMETERS}

    cases["cases"].append({"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                           "target_type": "baseline", "rationale": "Neutral site and actor reference only; not selected for capture.",
                           "variable_assignments": assignments("park", "outside", "hazardous"),
                           "unresolved_judgment_calls": [], "recording_description": RECORDING})
    for suffix, (conduct, footprint, context) in CASES.items():
        pair = ("inside_vs_outside" if suffix in ("park_inside_hazard", "park_outside_hazard")
                else "stop_stand_park" if suffix in ("stand_inside_hazard", "stop_inside_hazard")
                else "hazard_vs_congestion")
        variable = ("requested_footprint" if pair == "inside_vs_outside" else
                    "requested_conduct" if pair == "stop_stand_park" else
                    "place_context_for_review")
        cases["cases"].append({"case_id": ASSIGNMENT + "__" + suffix,
             "target_law_id": LAW,
             "target_type": "compliant_attempt" if footprint == "outside" else "violating_attempt",
             "rationale": "Controlled physical observation under separately sourced device and place facts; no legal verdict.",
             "variable_assignments": assignments(conduct, footprint, context),
             "unresolved_judgment_calls": ["official device status", "place character", "legal conduct category"],
             "recording_description": RECORDING,
             "paired_probe_id": pair,
             "deliberate_differences": [variable],
             "probe": {"primary_variable": variable,
                       "comparison_or_standard": "source-bound controlled contrast",
                       "target_value_or_branch": {"conduct": conduct, "footprint": footprint,
                                                  "place_context_for_review": context}}})
    write(PROPOSALS / "cases.json", cases)
    refs = {}
    for stage in ("relevance_batch", "relevance", "template", "bindings", "cases"):
        path = PROPOSALS / (stage + ".json")
        refs[stage] = {"path": "proposals/" + path.name, "sha256": sha(path)}
    refs["judgment_observables"] = []
    write(PROPOSALS / "semantic-index.json",
          {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
           "stages": refs})


if __name__ == "__main__":
    author()
