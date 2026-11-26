"""Complete the canonical draft stage chain around eight source-gated cases."""
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
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    law = assignment["law"]
    proposal = json.loads((OUT / "cases.json").read_text())
    template_id = law["id"] + "@" + assignment["actor"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
                 "relevant_laws": [{"law_id": law["id"], "quote": law["text"],
                                    "applies_to": [plan["actor"]],
                                    "relevance_type": "assigned posted-speed highway portion",
                                    "confidence": "medium",
                                    "notes": "Original public-authority and highway-portion sources pending."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    domains = {"travel_direction": "forward or opposite reviewed lane",
               "rate_relation": "below, equal or above requested relation; actual speed measured separately",
               "segment_mode": "governed or outside reviewed posted portion",
               "authority_mode": "public-authority or non-authority source",
               "unit_mode": "mph or km/h representation",
               "visibility_mode": "camera review or off-camera reading assumption"}
    params = [{"name": name, "kind": "controller" if name == "rate_relation" else "world_setup",
               "range_or_domain": domain} for name, domain in domains.items()]
    phrases = [{"phrase": "public authority", "note": ""},
               {"phrase": "particular portion of highway", "note": ""}]
    template = {"template_id": template_id, "law_id": law["id"], "actor": plan["actor"],
                "quote": law["text"], "structure": {
                    "law_id": law["id"],
                    "activation": {"condition": "Vehicle operates on the source-established posted highway portion and direction.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Actual speed is not greater than the applicable public-authority posted rate.",
                                   "type": "must_not", "numeric_conditions": []},
                    "exceptions": [],
                    "timing": {"description": "While traversing that highway portion.", "numeric_conditions": []},
                    "judgment_calls_needed": phrases},
                "parameter_refs": params}
    refs["template"] = write("template.json", template)
    refs["judgment_observables"] = []
    for index, phrase in enumerate(phrases):
        value = {"template_id": template_id, "phrase": phrase["phrase"], "note": "", "status": "draft",
                 "observable_requirements": {
                     "observables": [{"name": "actual_speed_mps", "unit": "m/s",
                                      "description": "Original per-frame ego velocity"},
                                     {"name": "governed_portion", "unit": "boolean",
                                      "description": "Original route and posting extent join"}],
                     "context_inputs": [{"name": "reviewed_posted_site", "unit": "source record",
                                         "description": "Highway, sign, posting authority, segment and direction sources"}],
                     "sweep_dimensions": [{"name": "source_status", "unit": "category",
                                           "description": "Original authority and route review alternatives"}],
                     "landmarks": [],
                     "recording_needs": [{"name": "actual_speed_mps", "unit": "m/s",
                                          "description": "Full original 20 Hz history"}],
                     "limitations": ["Original source packets and media are absent; no legal outcome assigned."]}}
        refs["judgment_observables"].append(write(f"judgment-{index}.json", value))
    binding = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
               "established_contexts": ["Narrow road; original highway and posting sources pending"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{**param, "used_by_laws": [law["id"]]} for param in params]}
    refs["bindings"] = write("bindings.json", binding)
    above = next(case for case in proposal["cases"] if case["case_id"].endswith("__above"))
    baseline = dict(above, case_id=ROOT.name + "__baseline", target_law_id=None,
                    target_type="baseline", rationale="Neutral source context; no new capture or legal label.",
                    unresolved_judgment_calls=[])
    baseline.pop("paired_probe_id", None)
    cases = [baseline]
    for case in proposal["cases"]:
        if case.get("target_type") == "baseline":
            continue
        suffix = case["case_id"].rsplit("__", 1)[-1]
        pair = next(item["comparison_id"] for item in plan["comparisons"]
                    if case["case_id"] in item["case_ids"])
        changes = [name for name, setting in case["variable_assignments"].items()
                   if setting["value"] != above["variable_assignments"][name]["value"]]
        primary = changes[0] if changes else "rate_relation"
        case.update(target_type="boundary_probe", paired_probe_id=pair,
                    deliberate_differences=changes or ["rate_relation"],
                    probe={"primary_variable": primary,
                           "comparison_or_standard": "same reviewed road and independent original source measurement",
                           "target_value_or_branch": case["variable_assignments"][primary]["value"]},
                    unresolved_judgment_calls=[item["phrase"] for item in phrases])
        cases.append(case)
    proposal["cases"] = cases
    proposal["sweeps_expanded"] = True
    proposal["semantic_status"] = "partial_original_source_review"
    for spec in proposal["sweep_specs"]:
        spec["judgment_refs"] = phrases
    refs["cases"] = write("cases.json", proposal)
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": ROOT.name, "stages": refs,
                                  "status": "partial_original_source_review"})
    print("canonical draft stages and", len(cases) - 1, "selected cases written")


if __name__ == "__main__":
    main()
