"""Write canonical draft stages for source-gated entry timing and exceptions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / "proposals"


def write(name, value):
    path = OUT / name
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposal = json.loads((OUT / "cases.json").read_text())
    law = assignment["law"]
    template_id = law["id"] + "@" + assignment["actor"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
                 "relevant_laws": [{"law_id": law["id"], "quote": law["text"],
                                    "applies_to": [plan["actor"]],
                                    "relevance_type": "assigned intersection entry timing",
                                    "confidence": "medium",
                                    "notes": "Official control and right-of-way sources pending."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    params = [{"name": "entry_time_difference_target_s", "kind": "controller",
               "range_or_domain": "frozen below, inside and above training range targets; actual entry measured independently"}]
    phrases = [{"phrase": "approximately the same time", "note": ""},
               {"phrase": "official traffic-control devices", "note": ""},
               {"phrase": "driver of the vehicle on the left", "note": ""}]
    template = {"template_id": template_id, "law_id": law["id"],
                "actor": plan["actor"], "quote": law["text"],
                "structure": {"law_id": law["id"],
                              "activation": {"condition": "Two vehicles enter from different highways at an intersection with source-reviewed applicability.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "The left vehicle yields to the right vehicle when the source-grounded conditions hold.",
                                             "type": "must", "numeric_conditions": []},
                              "exceptions": [
                                  {"description": "Official traffic-control-device intersection status requires independent authority review.",
                                   "source_clause": "this section does not apply at intersections controlled by official traffic-control devices",
                                   "numeric_conditions": []},
                                  {"description": "Opposing approach with an intended or actual left turn requires source review.",
                                   "source_clause": "or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn",
                                   "numeric_conditions": []},
                                  {"description": "Subsection 4 priority requires independent statutory review.",
                                   "source_clause": "Except as otherwise provided in subsection 4 [NRS-484B-250-4]",
                                   "numeric_conditions": []}],
                              "timing": {"description": "At the original footprint entry into the reviewed intersection.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": phrases},
                "parameter_refs": params}
    refs["template"] = write("template.json", template)
    refs["judgment_observables"] = []
    for index, item in enumerate(phrases):
        value = {"template_id": template_id, "phrase": item["phrase"], "note": "",
                 "status": "draft", "observable_requirements": {
                     "observables": [{"name": "intersection_entry_time_difference", "unit": "s",
                                      "description": "Original footprint entry brackets for both vehicles"}],
                     "context_inputs": [{"name": "reviewed_median_opening_site", "unit": "source record",
                                         "description": "Intersection, distinct highways, authority and left/right priority"}],
                     "sweep_dimensions": [{"name": "source_status", "unit": "category",
                                           "description": "Reviewed applicability and timing alternatives"}],
                     "landmarks": [],
                     "recording_needs": [{"name": "intersection_entry_time_difference", "unit": "s",
                                          "description": "Full original 20 Hz body footprint history"}],
                     "limitations": ["Original site and two-vehicle traces absent; no legal outcome assigned."]}}
        refs["judgment_observables"].append(write(f"judgment-{index}.json", value))
    binding = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
               "established_contexts": ["Median opening cell; actual official-device status pending"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{**param, "used_by_laws": [law["id"]]} for param in params]}
    refs["bindings"] = write("bindings.json", binding)
    inside = next(c for c in proposal["cases"] if c["case_id"].endswith("__entry_inside"))
    baseline = dict(inside, case_id=ROOT.name + "__baseline", target_law_id=None,
                    target_type="baseline", rationale="Neutral source context; no new capture or legal label.",
                    unresolved_judgment_calls=[])
    cases = [baseline]
    for case in proposal["cases"]:
        pair = next(x["comparison_id"] for x in plan["comparisons"]
                    if case["case_id"] in x["case_ids"])
        case.update(target_type="boundary_probe", paired_probe_id=pair,
                    deliberate_differences=["entry_time_difference_target_s"],
                    probe={"primary_variable": "entry_time_difference_target_s",
                           "comparison_or_standard": "same reviewed intersection and independently measured original entry time",
                           "target_value_or_branch": case["variable_assignments"]["entry_time_difference_target_s"]["value"]},
                    unresolved_judgment_calls=[p["phrase"] for p in phrases])
        cases.append(case)
    proposal["cases"] = cases
    proposal["sweeps_expanded"] = True
    for spec in proposal["sweep_specs"]:
        spec["judgment_refs"] = phrases
    refs["cases"] = write("cases.json", proposal)
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": ROOT.name, "stages": refs,
                                  "status": "partial_original_source_review"})
    print("canonical draft chain and", len(cases) - 1, "selected timing cases")


if __name__ == "__main__":
    main()
