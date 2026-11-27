"""Build source-scoped draft semantic stages for the C378245 taxi rule."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = "testing__C378245__LVMC-11-60-040__taxi_driver"
PHRASE = "expeditious loading or unloading of passengers"


def write(name: str, value: dict) -> None:
    target = ROOT / "proposals" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build() -> None:
    original = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    law = original["law"]
    assert original["assignment_id"] == plan["assignment_id"] == ASSIGNMENT
    quote = law["text"]
    relevance = {
        "cell_id": "C378245", "actor": "taxi_driver", "status": "draft",
        "relevant_laws": [{"law_id": law["id"], "quote": quote,
                           "applies_to": ["taxi_driver"],
                           "relevance_type": "selected business-district taxi stand and parking rule",
                           "confidence": "medium",
                           "notes": "Frozen cell selects this law; original site and official designation review remain pending."}],
        "borderline_excluded": [],
    }
    write("relevance_batch.json", relevance)
    write("relevance.json", relevance)
    refs = [
        {"name": "location_request", "kind": "world_setup",
         "range_or_domain": "inside or outside independently reviewed designated taxi stand"},
        {"name": "halt_activity_request", "kind": "controller",
         "range_or_domain": "park, stand, or temporary stop as engineering requests"},
        {"name": "passenger_exchange_request", "kind": "controller",
         "range_or_domain": "none, loading, or unloading as an engineering request"},
    ]
    template = {
        "template_id": law["id"] + "@taxi_driver", "law_id": law["id"],
        "actor": "taxi_driver", "quote": quote,
        "structure": {"law_id": law["id"],
                      "activation": {"condition": "Operator of a taxicab upon a street",
                                     "numeric_conditions": []},
                      "obligation": {"description": "Do not stand or park outside a designated taxicab stand",
                                     "type": "must_not", "numeric_conditions": []},
                      "exceptions": [{"source_clause": quote[quote.index("This provision"):],
                                      "description": "Actual expeditious loading or unloading during a temporary stop in accordance with other regulations"}],
                      "timing": {"description": "While the taxi stands or parks; during actual passenger loading or unloading for the exception",
                                 "numeric_conditions": []},
                      "judgment_calls_needed": [{"phrase": PHRASE,
                                                 "note": "No legal duration cutoff is supplied."}]},
        "parameter_refs": refs,
    }
    write("template.json", template)
    observable = {
        "template_id": template["template_id"], "phrase": PHRASE,
        "note": "No legal duration cutoff is supplied.",
        "observable_requirements": {
            "observables": [{"name": "passenger_activity_review", "unit": "source record",
                             "description": "Independent review of actual boarding or alighting and taxi halt interval"},
                            {"name": "taxi_speed_mps", "unit": "m/s",
                             "description": "Original taxi velocity during the reviewed halt"}],
            "context_inputs": [{"name": "other_stopping_parking_regulations", "unit": "source record",
                                "description": "Reviewed applicable other stopping or parking rules"}],
            "sweep_dimensions": [{"name": "halt_duration_s", "unit": "s",
                                  "description": "Observed duration of passenger-related taxi halt, without legal cutoff"}],
            "landmarks": [],
            "recording_needs": [{"name": "passenger_activity_review", "unit": "source record",
                                 "description": "Original independent activity review joined to Native camera frames"},
                                {"name": "taxi_speed_mps", "unit": "m/s",
                                 "description": "Original synchronized taxi velocity"}],
            "limitations": ["Expeditiousness cannot be settled by an invented seconds threshold.",
                            "Actual passenger exchange and other-rule compliance require independent review."],
        },
    }
    write("judgment-expeditiousness.json", observable)
    bindings = {
        "cell_id": "C378245", "actor": "taxi_driver", "status": "draft",
        "established_contexts": ["candidate business-district curb and taxi stand; original site source pending"],
        "law_refs": [{"template_id": template["template_id"], "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[law["id"]]) for item in refs],
    }
    write("bindings.json", bindings)
    draft = json.loads((ROOT / "proposals/cases.draft.json").read_text())
    cases = draft["cases"]
    for case in cases:
        suffix = case["case_id"].split("__")[-1]
        if suffix == "outside_stand_stand":
            case["target_type"] = "boundary_probe"
        if suffix in ("designated_stand_park", "outside_stand_park"):
            case["deterministic_branch"] = {
                "source_clause": quote[:quote.index(" This provision")],
                "judgment_context": [{"phrase": PHRASE,
                                      "note": "No legal duration cutoff is supplied.",
                                      "status": "not_exercised",
                                      "reason": "No passenger exchange is requested in this parking comparison.",
                                      "world_setup_refs": []}],
            }
    baseline = dict(cases[0],
                    case_id=ASSIGNMENT + "__baseline",
                    target_law_id=None, target_type="baseline",
                    rationale="Nonexecuted reference for fixed taxi, street and camera conditions.",
                    variable_assignments={name: dict(value, value="unselected")
                                          for name, value in cases[0]["variable_assignments"].items()})
    for key in ("paired_probe_id", "deliberate_differences", "probe", "deterministic_branch"):
        baseline.pop(key, None)
    cases.insert(0, baseline)
    result = {"cell_id": "C378245", "actor": "taxi_driver", "status": "draft",
              "cases": cases, "sweep_specs": [{
                  "sweep_id": "taxi_expeditiousness_pending",
                  "target_law_id": law["id"],
                  "judgment_refs": [{"phrase": PHRASE,
                                     "note": "No legal duration cutoff is supplied."}],
                  "status": "incomplete",
                  "missing_inputs": ["Source-reviewed feasible passenger loading/unloading mechanism and physical duration range",
                                     "Original independent activity review covering each planned physical interval"],
                  "rationale": "No defensible physical sweep range can be asserted before original passenger mechanism and site review."}]}
    write("cases.json", result)
    names = {"relevance_batch": "relevance_batch.json",
             "relevance": "relevance.json", "template": "template.json",
             "judgment_observables": "judgment-expeditiousness.json",
             "bindings": "bindings.json", "cases": "cases.json"}
    references = {stage: {"path": "proposals/" + name,
                          "sha256": hashlib.sha256((ROOT / "proposals" / name).read_bytes()).hexdigest()}
                  for stage, name in names.items()}
    references["judgment_observables"] = [references["judgment_observables"]]
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": ASSIGNMENT, "stages": references})


if __name__ == "__main__":
    build()
    print("six taxi semantic stages drafted")
