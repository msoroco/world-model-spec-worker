"""Draft exact-law semantic stages without resolving original-source judgments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_bundles import HERE, AID, recording_description

LAW = "NRS-484B-517"
ACTOR = "motor_vehicle_driver"
CELL = "C135087"
PARAMETERS = [
    {"name": "loading_mode", "kind": "world_setup", "range_or_domain": "active or ceased", "unit": "category"},
    {"name": "entrant_mode", "kind": "world_setup", "range_or_domain": "about_to_enter, waiting_to_enter, or no_entrant", "unit": "category"},
    {"name": "access_mode", "kind": "world_setup", "range_or_domain": "open or constrained", "unit": "category"},
]
JUDGMENTS = [
    {"phrase": "officially designated and appropriately signed", "note": "Stand and sign status need original site and authority review."},
    {"phrase": "temporarily stop", "note": "Duration alone does not establish the legal term."},
    {"phrase": "actually engaged in expeditiously loading or unloading of passengers", "note": "Observed activity and expedience need independent review."},
    {"phrase": "does not interfere with any bus or taxicab waiting to enter or about to enter such zone", "note": "Original access and entrant observations do not themselves decide interference."},
]


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    assignment = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    if (assignment["law_id"], assignment["cell_id"], assignment["actor"]) != (LAW, CELL, ACTOR) or plan["law_text"] != quote:
        raise ValueError("frozen exact law identity changed")
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR], "confidence": "high"}],
                 "borderline_excluded": []}
    template_id = LAW + "@" + ACTOR
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR, "status": "draft",
                "quote": quote, "parameter_refs": PARAMETERS,
                "structure": {"activation": {"source_clause": "when such stop or stand has been officially designated and appropriately signed"},
                              "obligation": {"source_clause": "A person shall not stop, stand or park a vehicle other than a bus in a bus stop, or a taxicab in a taxicab stand"},
                              "exceptions": [{"source_clause": "except that the driver of a passenger vehicle may temporarily stop there and for the purpose of and while actually engaged in expeditiously loading or unloading of passengers when such stopping does not interfere with any bus or taxicab waiting to enter or about to enter such zone", "trigger": "passenger vehicle loading exception", "effect": "conditional stop permission", "replacement_obligation": "source reviewed loading and noninterference"}],
                              "timing": {"source_clause": "while actually engaged in expeditiously loading or unloading of passengers"},
                              "judgment_calls_needed": JUDGMENTS}}
    refs = {"relevance_batch": write("relevance-batch.json", relevance),
            "relevance": write("relevance.json", relevance), "template": write("template.json", template)}
    observed = []
    for index, judgment in enumerate(JUDGMENTS):
        row = {"template_id": template_id, "status": "draft", **judgment,
               "observable_requirements": {
                   "observables": [{"name": "loading, waiting, entry and access", "unit": "source observation", "description": "Original 900-frame 20 Hz Native observation"},
                                   {"name": "four synchronized camera views", "unit": "source observation", "description": "Original 20 Hz Native video"}],
                   "context_inputs": [{"name": "reviewed stand, sign, map and vehicle classification sources", "unit": "source record", "description": "Independent original authority and classification evidence"}],
                   "sweep_dimensions": [], "landmarks": [],
                   "recording_needs": [{"name": "loading, waiting, entry and access", "unit": "source observation", "description": "Source-sealed Native readback"}],
                   "limitations": ["Physical observations do not settle the legal judgment without original source review."]}}
        observed.append(write(f"judgment-{index}.json", row))
    refs["judgment_observables"] = observed
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [dict(row, used_by_laws=[LAW]) for row in PARAMETERS]}
    refs["bindings"] = write("bindings.json", binding)
    desc = recording_description()
    def assignments(source):
        return {row["name"]: {"kind": row["kind"], "unit": row["unit"], "value": source[row["name"]]}
                for row in PARAMETERS}
    baseline = {"case_id": AID + "__baseline", "target_law_id": None, "target_type": "baseline",
                "rationale": "Shared source observation schema; no separate recording.",
                "variable_assignments": assignments(plan["cases"][0]),
                "recording_description": desc, "unresolved_judgment_calls": JUDGMENTS}
    cases = [baseline]
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
                      "target_type": "judgment_sweep", "rationale": case["purpose"],
                      "variable_assignments": assignments(case), "recording_description": desc,
                      "unresolved_judgment_calls": JUDGMENTS,
                      "paired_probe_id": suffix, "deliberate_differences": ["loading_mode", "entrant_mode", "access_mode"],
                      "probe": {"primary_variable": "access_mode", "comparison_or_standard": "Original source observations; no legal verdict", "target_value_or_branch": suffix}})
    sweeps = [{"sweep_id": f"stand_judgment_{index}_source_pending", "target_law_id": LAW,
               "judgment_refs": [judgment], "status": "incomplete",
               "rationale": "Original site, vehicle classification and feasible source-backed motion are not reviewed.",
               "missing_inputs": ["Reviewed original stand/sign and actor source packet and feasible Native variation"]}
              for index, judgment in enumerate(JUDGMENTS)]
    stage = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": cases,
             "sweep_specs": sweeps, "comparisons": plan["comparisons"],
             "source_law_text": quote, "source_assignment": "inputs/" + AID + "/assignment.json"}
    refs["cases"] = write("cases.json", stage)
    write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID, "stages": refs})
    print("draft semantic stages:", len(cases) - 1, "selected cases,", len(sweeps), "source-pending judgments")


if __name__ == "__main__":
    build()
