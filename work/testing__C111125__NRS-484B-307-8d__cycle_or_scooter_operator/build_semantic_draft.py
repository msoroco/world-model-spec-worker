"""Build source-faithful NRS 484B.307(8)(d) proposal stages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_offline_draft import recording_description

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = "NRS-484B-307-8d"
ACTOR = "cycle_or_scooter_operator"
CELL = "C111125"
PARAMETERS = [
    {"name": "full_cycles_after_stop_target", "kind": "controller", "unit": "cycles",
     "range_or_domain": "one, two or three complete observed device cycles"},
    {"name": "stop_pattern", "kind": "controller", "unit": "categorical",
     "range_or_domain": "stopped or rolling before the source-bound stop boundary"},
    {"name": "detector_output_target", "kind": "world_setup", "unit": "categorical",
     "range_or_domain": "suppressed or responsive; original causal authority separately reviewed"},
    {"name": "participant_conflict_target", "kind": "world_setup", "unit": "categorical",
     "range_or_domain": "clear or occupied by a signal-directed participant"},
]
JUDGMENTS = [
    {"phrase": "because of a malfunction or because the signal failed to detect the presence of the motorcycle, moped, trimobile, bicycle, electric bicycle or electric scooter",
     "note": "Original detector output and subject red alone do not establish causation or malfunction."},
    {"phrase": "yields the right-of-way to pedestrians and other traffic proceeding as directed by the signal at the intersection",
     "note": "Physical occupancy alone does not establish directed or lawful right-of-way status."},
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
        raise ValueError("Exact frozen identity changed")
    quote = assignment["law"]["text"]
    if quote != plan["law_text"] or len(plan["cases"]) != 6:
        raise ValueError("Exact law or six-case plan changed")
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "confidence": "high"}], "borderline_excluded": []}
    template_id = LAW + "@" + ACTOR
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote, "parameter_refs": PARAMETERS,
                "structure": {
                    "activation": {"source_clause": "Where the signal is a steady red signal alone"},
                    "obligation": {"source_clause": "The person waits for two complete cycles of the lights or lighted arrows of the applicable official traffic-control device",
                                   "numeric_conditions": [{"variable": "full_cycles_after_stop_target",
                                                           "operator": ">=", "value": 2, "unit": "cycles"}]},
                    "exceptions": [],
                    "timing": {"source_clause": "After complying with the requirement to stop"},
                    "judgment_calls_needed": JUDGMENTS}}
    refs = {"relevance_batch": write("relevance-batch.json", relevance),
            "relevance": write("relevance.json", relevance),
            "template": write("template.json", template)}
    observable_refs = []
    for index, judgment in enumerate(JUDGMENTS):
        channel = "detector zone and output" if index == 0 else "signal-directed pedestrians and traffic"
        context = "reviewed map, official device, detector, bicycle and rider authority"
        observable = {"template_id": template_id, "status": "draft", **judgment,
                      "observable_requirements": {
                          "observables": [{"name": channel, "unit": "source observation",
                                           "description": "Original source-bound 20 Hz readback"}],
                          "context_inputs": [{"name": context, "unit": "source record",
                                              "description": "Exact hashed site, device, detector and rider authority"}],
                          "sweep_dimensions": [], "landmarks": [],
                          "recording_needs": [{"name": channel, "unit": "source observation",
                                               "description": "Original saved channel and camera review"}],
                          "limitations": [judgment["note"]]}}
        observable_refs.append(write("judgment-" + str(index) + ".json", observable))
    refs["judgment_observables"] = observable_refs
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in PARAMETERS]}
    refs["bindings"] = write("bindings.json", binding)
    baseline = {"full_cycles_after_stop_target": 2, "stop_pattern": "stopped",
                "detector_output_target": "suppressed", "participant_conflict_target": "clear"}
    variants = {
        "two_cycles_failed_detection": (2, "stopped", "suppressed", "clear"),
        "one_cycle": (1, "stopped", "suppressed", "clear"),
        "three_cycles": (3, "stopped", "suppressed", "clear"),
        "signal_changes": (2, "stopped", "responsive", "clear"),
        "no_prior_stop": (2, "rolling", "suppressed", "clear"),
        "fails_to_yield": (2, "stopped", "suppressed", "occupied"),
    }
    description = recording_description()
    def assignments(values):
        return {p["name"]: {"kind": p["kind"], "unit": p["unit"], "value": values[p["name"]]}
                for p in PARAMETERS}
    cases = [{"case_id": AID + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared source observation definition; no separate recording.",
              "variable_assignments": assignments(baseline),
              "recording_description": description, "unresolved_judgment_calls": JUDGMENTS}]
    for item in plan["cases"]:
        suffix = item["case_id"].removeprefix(AID + "__")
        cycles, stop, detector, conflict = variants[suffix]
        values = dict(zip(baseline, (cycles, stop, detector, conflict)))
        cycle_probe = suffix in ("one_cycle", "two_cycles_failed_detection", "three_cycles")
        variable = ("full_cycles_after_stop_target" if cycle_probe else
                    "detector_output_target" if suffix == "signal_changes" else
                    "stop_pattern" if suffix == "no_prior_stop" else "participant_conflict_target")
        row = {"case_id": item["case_id"], "target_law_id": LAW,
               "target_type": "boundary_probe" if cycle_probe else "judgment_sweep",
               "rationale": item["purpose"], "variable_assignments": assignments(values),
               "recording_description": description, "unresolved_judgment_calls": JUDGMENTS,
               "paired_probe_id": "complete_cycle_count" if cycle_probe else suffix,
               "deliberate_differences": [variable],
               "probe": {"primary_variable": variable,
                         "comparison_or_standard": "Original source measurements only; no legal verdict",
                         "target_value_or_branch": cycles if cycle_probe else suffix}}
        if cycle_probe:
            row["epsilon_used"] = 1
            row["probe"].update({"threshold_ref": "obligation.numeric_conditions[0]",
                                 "operator": ">=", "unit": "cycles", "test_value": cycles})
        cases.append(row)
    sweeps = [{"sweep_id": "source_pending_" + str(i), "target_law_id": LAW,
               "judgment_refs": [judgment], "status": "incomplete",
               "rationale": "Original causal or right-of-way source variation has not been reviewed.",
               "missing_inputs": [judgment["note"]]}
              for i, judgment in enumerate(JUDGMENTS)]
    refs["cases"] = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
                                            "status": "draft", "cases": cases,
                                            "sweep_specs": sweeps,
                                            "comparisons": plan["comparisons"],
                                            "source_law_text": quote,
                                            "source_assignment": "inputs/" + AID + "/assignment.json"})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "stages": refs})
    print("source-faithful six-case semantic draft")


if __name__ == "__main__":
    build()
