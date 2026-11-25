"""Build exact-source semantic proposals without resolving lawful-status judgments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_offline_draft import recording_description
from lawful_status_sweep import source_gated_specs

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = "NRS-484B-307-9b"
ACTOR = "motorcycle_or_moped_operator"
CELL = "C111125"
JUDGMENTS = [
    {"phrase": "pedestrians lawfully within an adjacent crosswalk",
     "note": "Original crosswalk occupancy alone does not establish lawful status."},
    {"phrase": "other traffic lawfully using the intersection",
     "note": "Original intersection occupancy alone does not establish lawful status."},
]
PARAMETERS = [
    {"name": "full_cycles_after_stop_target", "kind": "controller",
     "range_or_domain": "one, two or three complete source-observed aspect-return cycles", "unit": "cycles"},
    {"name": "stop_pattern", "kind": "controller",
     "range_or_domain": "stopped or rolling", "unit": "categorical stop request"},
    {"name": "unchanged_signal_cause_target", "kind": "world_setup",
     "range_or_domain": "source-affirmed failed detection or not established", "unit": "categorical causal source"},
    {"name": "other_user_region_at_entry", "kind": "world_setup",
     "range_or_domain": "clear, adjacent crosswalk or intersection with separate lawful-status source", "unit": "categorical participant region"},
]


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if (assignment["law_id"], assignment["cell_id"], assignment["actor"]) != (LAW, CELL, ACTOR):
        raise ValueError("frozen assignment identity changed")
    if len(plan["cases"]) != 7 or plan["law_text"] != assignment["law"]["text"]:
        raise ValueError("exact law or seven-case boundary plan changed")
    quote = plan["law_text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "confidence": "high"}], "borderline_excluded": []}
    template_id = LAW + "@" + ACTOR
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote, "parameter_refs": PARAMETERS,
                "structure": {
                    "activation": {"source_clause": "Where the signal is a steady red with a green turn arrow"},
                    "obligation": {"source_clause": "The person waits for two complete cycles of the lights or lighted arrows of the applicable official traffic-control device",
                                   "numeric_conditions": [{"variable": "full_cycles_after_stop_target", "operator": ">=", "value": 2, "unit": "cycles"}]},
                    "exceptions": [],
                    "timing": {"source_clause": "before entering the intersection"},
                    "judgment_calls_needed": JUDGMENTS}}
    refs = {"relevance_batch": write("relevance-batch.json", relevance),
            "relevance": write("relevance.json", relevance),
            "template": write("template.json", template)}
    observable_refs = []
    for index, judgment in enumerate(JUDGMENTS):
        name = "crosswalk" if index == 0 else "traffic"
        observable = {"template_id": template_id, "status": "draft", **judgment,
                      "observable_requirements": {
                          "observables": [
                              {"name": "crosswalk pedestrian and lawful traffic tracks",
                               "unit": "source observation", "description": "Original participant region and movement at 20 Hz"},
                              {"name": "four synchronized original camera views",
                               "unit": "source observation", "description": "Same-frame physical visibility review"}],
                          "context_inputs": [{"name": "reviewed map, route, head, stop hierarchy, causal device and participant authority",
                                              "unit": "source record", "description": "Independent lawful-status source and exact site hash"}],
                          "sweep_dimensions": [], "landmarks": [],
                          "recording_needs": [{"name": "crosswalk pedestrian and lawful traffic tracks",
                                               "unit": "source observation", "description": "Original movement and independent lawful-status source"}],
                          "limitations": ["Lawful status cannot be inferred from physical occupancy or diagnostic fixture labels."]}}
        observable_refs.append(write("judgment-" + name + ".json", observable))
    refs["judgment_observables"] = observable_refs
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [dict(p, used_by_laws=[LAW]) for p in PARAMETERS]}
    refs["bindings"] = write("bindings.json", binding)
    description = recording_description()
    neutral = {p["name"]: {"kind": p["kind"], "unit": p["unit"],
                           "value": None if p["kind"] == "subject_behavior" else
                           plan["cases"][0]["scenario_parameters"][p["name"]]} for p in PARAMETERS}
    cases = [{"case_id": AID + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared source-observation definition; no separate recording.",
              "variable_assignments": neutral, "recording_description": description,
              "unresolved_judgment_calls": JUDGMENTS}]
    probe_pair = {"one_cycle_entry": ("complete_cycle_count", "full_cycles_after_stop_target", ["full_cycles_after_stop_target"]),
                  "two_cycles_clear": ("complete_cycle_count", "full_cycles_after_stop_target", ["full_cycles_after_stop_target"]),
                  "three_cycles_clear": ("complete_cycle_count", "full_cycles_after_stop_target", ["full_cycles_after_stop_target"]),
                  "rolling_entry": ("stopping_event", "stop_pattern", ["stop_pattern", "full_cycles_after_stop_target"]),
                  "no_causal_record": ("causal_record", "unchanged_signal_cause_target", ["unchanged_signal_cause_target"]),
                  "pedestrian_crosswalk": ("crosswalk_yield", "other_user_region_at_entry", ["other_user_region_at_entry"]),
                  "lawful_traffic": ("intersection_yield", "other_user_region_at_entry", ["other_user_region_at_entry"])}
    for source in plan["cases"]:
        suffix = source["case_id"].removeprefix(AID + "__")
        pair, variable, differences = probe_pair[suffix]
        values = {p["name"]: {"kind": p["kind"], "unit": p["unit"],
                              "value": source["scenario_parameters"][p["name"]]} for p in PARAMETERS}
        row = {"case_id": source["case_id"], "target_law_id": LAW,
               "target_type": "boundary_probe" if suffix in ("one_cycle_entry", "two_cycles_clear", "three_cycles_clear") else "judgment_sweep",
               "rationale": source["purpose"], "variable_assignments": values,
               "recording_description": description, "unresolved_judgment_calls": JUDGMENTS,
               "paired_probe_id": pair, "deliberate_differences": differences,
               "probe": {"primary_variable": variable,
                         "comparison_or_standard": "Original source measurements only; no legal verdict",
                         "target_value_or_branch": suffix}}
        if row["target_type"] == "boundary_probe":
            row["epsilon_used"] = 1
            row["probe"].update({"threshold_ref": "obligation.numeric_conditions[0]",
                                 "operator": ">=", "unit": "cycles",
                                 "test_value": source["scenario_parameters"]["full_cycles_after_stop_target"]})
        cases.append(row)
    sweep_specs = source_gated_specs()
    case_stage = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": cases,
                  "sweep_specs": sweep_specs, "sweeps_expanded": True,
                  "comparisons": plan["comparisons"],
                  "source_law_text": quote, "source_assignment": "inputs/" + AID + "/assignment.json"}
    refs["cases"] = write("cases.json", case_stage)
    write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
                                  "stages": refs})
    print("draft semantic stages: baseline, seven exact cases, two source-gated lawful-status sweeps")


if __name__ == "__main__":
    build()
