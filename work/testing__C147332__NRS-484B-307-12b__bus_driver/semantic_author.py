"""Author exact draft canonical stages for the red-X bus comparison set."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_constructions import recording_description
from bus_route import ROUTES


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
LAW = "NRS-484B-307-12b"
ACTOR = "bus_driver"
CELL = "C147332"


def write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def variables(kind):
    start = "governed" if kind in ("red_lane_stand", "red_lane_drive") else "adjacent"
    return {
        "overhead_red_x_setup": {"kind": "world_setup", "value": "reviewed_overhead_red_x_target",
                                 "note": "Original device and pixels must establish realization"},
        "bus_start_lane": {"kind": "world_setup", "value": start,
                           "note": "Original bus footprint and imported map must establish lane"},
        "bus_route_request": {"kind": "controller", "value": kind,
                              "note": "Control request; original motion measured independently"},
    }


def main():
    law = json.loads((ROOT.parents[1] / "inputs" / ASSIGNMENT / "assignment.json").read_text())["law"]
    quote = law["text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "relevance_type": "direct overhead lane signal facing bus",
                                    "confidence": "medium",
                                    "notes": "The one-way multilane cell can support the branch; official device and highway source review remain required."}],
                 "borderline_excluded": []}
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    template_id = LAW + "@" + ACTOR
    parameters = [
        {"name": "overhead_red_x_setup", "kind": "world_setup",
         "range_or_domain": "source-reviewed bus-facing overhead red X and governed lane"},
        {"name": "bus_start_lane", "kind": "world_setup",
         "range_or_domain": "adjacent or governed right-side lane"},
        {"name": "bus_route_request", "kind": "controller",
         "range_or_domain": "adjacent travel, lateral entry, governed-lane hold or travel"},
    ]
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
                "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "An overhead signal applies to the individual highway lane and faces the bus driver.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Under a red X, the facing driver must not enter or drive in the governed lane.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Entry and in-lane driving are observed while red X is shown.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": []},
                "parameter_refs": parameters}
    template_ref = write("template.json", template)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": ["one-way multilane target geometry", "bus route targets"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{**item, "used_by_laws": [LAW]} for item in parameters]}
    binding_ref = write("bindings.json", binding)
    description = recording_description()
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared red-X bus lane and source-review target.",
                "variable_assignments": variables("adjacent_travel"),
                "recording_description": description,
                "unresolved_judgment_calls": []}
    cases = [baseline]
    for kind in ROUTES:
        pair = "red_x_lateral_entry" if kind in ("adjacent_travel", "lateral_entry") else "red_x_in_lane_driving"
        cases.append({"case_id": ASSIGNMENT + "__" + kind,
                      "target_law_id": LAW,
                      "target_type": "compliant_attempt" if kind in ("adjacent_travel", "red_lane_stand") else "violating_attempt",
                      "rationale": "Requested bus route under a reviewed red X; realized behavior and legal judgment remain unconfirmed.",
                      "variable_assignments": variables(kind),
                      "recording_description": description,
                      "unresolved_judgment_calls": [],
                      "paired_probe_id": pair,
                      "deliberate_differences": ["bus_route_request"],
                      "probe": {"primary_variable": "bus_route_request",
                                "comparison_or_standard": "Original bus footprint and longitudinal motion while facing the same red X",
                                "target_value_or_branch": kind}})
    cases_ref = write("cases.json", {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                                      "cases": cases, "sweep_specs": []})
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                        "template": template_ref, "judgment_observables": [],
                        "bindings": binding_ref, "cases": cases_ref}}
    write("semantic-index.json", index)
    print(json.dumps({"selected_cases": len(ROUTES), "judgment_phrases": 0,
                      "source_review_required": True}))


if __name__ == "__main__":
    main()
