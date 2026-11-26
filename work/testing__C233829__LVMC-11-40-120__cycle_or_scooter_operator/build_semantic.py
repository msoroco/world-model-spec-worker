"""Author canonical adjacent-path proposals with original judgment open."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from path_observation import ASSIGNMENT


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "LVMC-11-40-120"
ACTOR = "cycle_or_scooter_operator"
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = assignment["law"]["text"]
    relevance = {"cell_id": "C233829", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "high"}],
                 "borderline_excluded": []}
    relevance_ref = write("relevance.json", relevance)
    write("relevance-batch.json", relevance)
    judgments = [
        ("usable path", "Original condition, physical continuity and access restrictions require independent review.", "path_context"),
        ("provided adjacent to a roadway", "Municipal designation, extent and relationship to the roadway require original source review.", "path_context"),
    ]
    params = [
        {"name": "device_type", "kind": "world_setup", "range_or_domain": "bicycle, electric bicycle or electric scooter", "unit": "category"},
        {"name": "rider_facility", "kind": "controller", "range_or_domain": "designated path or roadway", "unit": "category"},
        {"name": "path_usability_context", "kind": "world_setup", "range_or_domain": "usable or unusable after source review", "unit": "category"},
        {"name": "roadway_use_observed", "kind": "subject_behavior", "range_or_domain": "original body occupancy", "unit": "boolean"},
        {"name": "path_use_observed", "kind": "subject_behavior", "range_or_domain": "original body occupancy", "unit": "boolean"},
    ]
    template_ref = write("template.json", {"template_id": TEMPLATE, "law_id": LAW,
        "actor": ACTOR, "status": "draft", "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Usable provided path for a covered rider is adjacent to a roadway.", "numeric_conditions": []},
            "obligation": {"description": "Covered rider uses the path and does not use the roadway.", "type": "must", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Observe the rider and path throughout the original route.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments]},
        "parameter_refs": params})
    jrefs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        jrefs.append(write(f"judgment-{index}.json", {"template_id": TEMPLATE,
            "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {"observables": [{"name": channel,
                "unit": "source context", "description": note}],
                "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": channel, "unit": "source context", "description": note}],
                "limitations": ["Original physical usability and designation review remains local; no numeric legal cutoff is supplied."]}}))
    binding_ref = write("bindings.json", {"cell_id": "C233829", "actor": ACTOR,
        "status": "draft", "law_refs": [{"template_id": TEMPLATE,
                                       "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in params]})
    cases = []
    for row in plan["cases"]:
        cid = row["case_id"]
        name = cid.removeprefix(ASSIGNMENT + "__")
        construction = json.loads((HERE / ("construction-" + name + ".json")).read_text())
        values = {"device_type": row["device_type"],
                  "rider_facility": row["rider_facility"],
                  "path_usability_context": row["path_usability_context"]}
        assignments = {item["name"]: {"kind": item["kind"],
            "value": values.get(item["name"]), "unit": item["unit"]} for item in params}
        cases.append({"case_id": cid, "target_law_id": LAW,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Exact covered-device, path/roadway and reviewed usability construction; no legal verdict.",
            "paired_probe_id": "adjacent_path_route_and_condition",
            "deliberate_differences": ["device_type", "rider_facility", "path_usability_context"],
            "probe": {"primary_variable": "rider_facility",
                      "comparison_or_standard": "Compare original rider body occupancy with fixed source path context.",
                      "target_value_or_branch": name},
            "variable_assignments": assignments,
            "unresolved_judgment_calls": [item[0] for item in judgments],
            "recording_description": construction["recording_description"]})
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "status": "draft",
                "rationale": "Shared adjacent path context without legal finding.",
                "variable_assignments": cases[0]["variable_assignments"],
                "unresolved_judgment_calls": [item[0] for item in judgments],
                "recording_description": cases[0]["recording_description"]}
    sweep = {"sweep_id": "reviewed_adjacent_path_context", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments],
        "status": "incomplete", "mode": "joint", "axes": [], "landmarks": [],
        "rationale": "Original path condition and access sources must define physical variation before a fixed judgment sweep can be specified.",
        "missing_inputs": ["reviewed municipal path designation and adjacency",
                           "original path condition, continuity and access survey"],
        "variable_assignments": cases[0]["variable_assignments"],
        "recording_description": cases[0]["recording_description"]}
    cases_ref = write("cases.json", {"cell_id": "C233829", "actor": ACTOR,
        "status": "draft", "sweep_specs": [sweep], "sweeps_expanded": True,
        "cases": [baseline, *cases]})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": jrefs,
                   "bindings": binding_ref, "cases": cases_ref},
        "status": "draft_original_source_pending"})


if __name__ == "__main__":
    main()
