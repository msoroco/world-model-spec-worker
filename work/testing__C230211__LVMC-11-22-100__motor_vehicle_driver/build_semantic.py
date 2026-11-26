"""Draft the six canonical semantic stages for exact protected-pavement cases."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, ACTOR, CELL, LAW, RECORDING

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "proposals"
ASSIGNMENT = json.loads((ROOT / "inputs" / AID / "assignment.json").read_text())
PLAN = json.loads((HERE / "case-plan.json").read_text())
LAW_TEXT = ASSIGNMENT["law"]["text"]
TEMPLATE_ID = LAW + "@" + ACTOR
JUDGMENTS = [
    {"phrase": "at or near", "note": "Warning location relative to protected pavement is preserved for review without an invented legal distance."},
    {"phrase": "actually engaged", "note": "Same-pavement active work and driver employment require source and timing review."}
]
PARAMS = [
    {"name": "protection_kind", "kind": "world_setup",
     "range_or_domain": "barrier across/around, warning person/sign or closed-highway sign",
     "unit": "source request"},
    {"name": "route_kind", "kind": "world_setup",
     "range_or_domain": "cross protected pavement or bypass",
     "unit": "source request"},
    {"name": "employee_engaged", "kind": "world_setup",
     "range_or_domain": "driver is or is not an employee actively paving or repairing the same pavement",
     "unit": "source request"}
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def requirements(phrase):
    if phrase == "at or near":
        needs = [("protection_geometry", "world meters", "Original warning position and geometry"),
                 ("pavement_extent", "world meters", "Original surveyed pavement extent")]
    else:
        needs = [("employment", "source record", "Driver employment and same-pavement identity"),
                 ("work_activity", "original time", "Active paving or repair during passage")]
    items = [{"name": name, "unit": unit, "description": description}
             for name, unit, description in needs]
    context = [{"name": "reviewed_native_pavement_site", "unit": "source record",
                "description": "Source-sealed pavement, warning, vehicle and work context"}]
    return {"observables": items, "context_inputs": context,
            "sweep_dimensions": [], "landmarks": [], "recording_needs": items,
            "limitations": ["Diagnostic measurements are not a legal distance or employee determination."]}


def build():
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW,
                                    "quote": "No person shall ride or drive any horse or vehicle over or across any pavement newly laid or repaired",
                                    "applies_to": [ACTOR], "confidence": "high"}],
                 "borderline_excluded": []}
    refs = {}
    refs["relevance_batch"] = write("relevance-batch.json", relevance)
    refs["relevance"] = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": LAW_TEXT,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Person rides or drives a vehicle over or across newly laid or repaired pavement protected by a barrier, warning person or sign, or closed-highway sign.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Do not ride or drive over or across such pavement.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [{"trigger": "Employee actually engaged in paving or repair of that same pavement",
                                              "effect": "Section does not apply",
                                              "replacement_obligation": None,
                                              "source_clause": "The provisions of this Section shall not apply to the employees actually engaged in the paving or repair of such pavement."}],
                              "timing": {"description": "Protection placed before vehicle passage; employee work concurrent with passage.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": JUDGMENTS},
                "parameter_refs": PARAMS}
    refs["template"] = write("template.json", template)
    refs["judgment_observables"] = []
    for index, judgment in enumerate(JUDGMENTS):
        proposal = {"template_id": TEMPLATE_ID, **judgment, "status": "draft",
                    "observable_requirements": requirements(judgment["phrase"])}
        refs["judgment_observables"].append(write("judgment-" + str(index) + ".json", proposal))
    bindings = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "established_contexts": [],
                "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{**p, "used_by_laws": [LAW]} for p in PARAMS]}
    refs["bindings"] = write("bindings.json", bindings)
    baseline = {"protection_kind": "barrier_across", "route_kind": "cross",
                "employee_engaged": False}
    def assignments(values):
        return {name: {"kind": "world_setup", "value": value,
                       "unit": "source request"} for name, value in values.items()}
    proposal_cases = [{"case_id": AID + "__baseline", "target_law_id": None,
                       "target_type": "baseline", "status": "draft",
                       "rationale": "Shared source-reviewed pavement and driver context; no accepted recording or legal outcome.",
                       "variable_assignments": assignments(baseline),
                       "unresolved_judgment_calls": [j["phrase"] for j in JUDGMENTS],
                       "recording_description": RECORDING}]
    for case in PLAN["cases"]:
        values = {"protection_kind": case["protection"],
                  "route_kind": case["route_kind"],
                  "employee_engaged": case["employee_engaged"]}
        differences = [name for name in baseline if values[name] != baseline[name]]
        variable = differences[0] if differences else "protection_kind"
        proposal_cases.append({"case_id": case["case_id"],
                               "target_law_id": LAW, "target_type": "boundary_probe",
                               "status": "draft",
                               "rationale": "Original source-backed protection, passage and work facts; no numeric legal cutoff or verdict.",
                               "paired_probe_id": "protected-pavement-branches",
                               "deliberate_differences": differences,
                               "variable_assignments": assignments(values),
                               "unresolved_judgment_calls": [j["phrase"] for j in JUDGMENTS],
                               "recording_description": RECORDING,
                               "probe": {"primary_variable": variable,
                                         "comparison_or_standard": "controlled same-pavement source and exact branch comparisons",
                                         "target_value_or_branch": values[variable]}})
    cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
             "sweep_specs": [{"sweep_id": "protected-pavement-judgment-review",
                              "target_law_id": LAW, "judgment_refs": JUDGMENTS,
                              "status": "incomplete",
                              "rationale": "No source-backed legal numeric standard exists for near placement or actually engaged work; exact factual branch cases remain runnable.",
                              "missing_inputs": ["Original warning location and time, same-pavement work evidence and independent legal review"]}],
             "sweeps_expanded": True, "cases": proposal_cases}
    refs["cases"] = write("cases.json", cases)
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "stages": refs})
    return len(proposal_cases)


if __name__ == "__main__":
    print("canonical cases including baseline:", build())
