"""Build source-preserving current-runtime semantic drafts for the exact alley pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = "LVMC-11-22-010"
ACTOR = "motor_vehicle_driver"
CELL = "C10301"
PHRASE = "full time and attention"


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recording_description(source: dict) -> dict:
    """Keep every frozen observation and add current runtime sampling metadata."""
    result = json.loads(json.dumps(source))
    for channel in result["channels"]:
        rate = channel.pop("rate_hz")
        channel.update(sampling_rate_hz=rate,
                       time_window="full original 45-second alley operation",
                       reference_frame="same original Native frame and simulation time",
                       uncertainty="20 Hz sampling; exterior motion does not observe interior attention")
    return result


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = plan["law_text"]
    if PHRASE not in quote or len(plan["cases"]) != 2:
        raise ValueError("Frozen law or exact alley pair changed")
    assignment = json.loads((HERE.parents[1] / "inputs" / AID / "assignment.json").read_text())
    if assignment["cell_id"] != CELL or assignment["law_id"] != LAW:
        raise ValueError("Frozen assignment identity changed")
    proposal_dir = HERE / "proposals"
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                     "applies_to": [ACTOR], "relevance_type": "assigned vehicle-operation duty",
                     "confidence": "medium",
                     "notes": "Municipal applicability and statutory vehicle-operation source review remain unresolved."}],
                 "borderline_excluded": []}
    template_id = LAW + "@" + ACTOR
    parameters = [
        {"name": "lateral_controller_profile", "kind": "controller",
         "range_or_domain": "steady alley tracking or preplanned mild variation"},
        {"name": "observed_attention_state", "kind": "subject_behavior",
         "range_or_domain": "unobserved in exterior Native recording"},
    ]
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
                "quote": quote,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "A person is operating a vehicle in the municipality; jurisdiction and operation require source review.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Give full time and attention to operation of the vehicle.",
                                   "type": "must", "numeric_conditions": []},
                    "exceptions": [], "timing": {"description": "While operating the vehicle.", "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": PHRASE, "note": "Exterior motion cannot determine interior attention."}]},
                "parameter_refs": parameters}
    observables = {"template_id": template_id, "phrase": PHRASE,
                   "note": "Exterior motion cannot determine interior attention.",
                   "observable_requirements": {
                       "observables": [{"name": v["name"], "unit": v["unit"],
                           "description": v["method"]} for v in plan["cases"][0]["recording_description"]["channels"]],
                       "context_inputs": [{"name": v["name"], "unit": v["unit"],
                           "description": v["method"]} for v in plan["cases"][0]["recording_description"]["context_inputs"]],
                       "sweep_dimensions": [], "landmarks": [],
                       "recording_needs": [{"name": "kin.position", "unit": "m",
                           "description": "Exterior trajectory as an observation only."}],
                       "limitations": list(plan["cases"][0]["recording_description"]["limitations"])}}
    bindings = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "established_contexts": ["Assigned alley travel context; source designation and municipal applicability pending review."],
                "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [dict(p, used_by_laws=[LAW]) for p in parameters]}
    cases = [{"case_id": AID + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Nonexecuted neutral semantic definition for the controlled alley pair.",
              "variable_assignments": {
                  "lateral_controller_profile": {"kind": "controller", "value": "unselected"},
                  "observed_attention_state": {"kind": "subject_behavior", "value": None}},
              "recording_description": recording_description(plan["cases"][0]["recording_description"]),
              "unresolved_judgment_calls": [PHRASE]}]
    for source in plan["cases"]:
        kind = source["case_id"].rsplit("__", 1)[-1]
        cases.append({"case_id": source["case_id"], "target_law_id": LAW,
                      "target_type": "judgment_sweep",
                      "rationale": "Exterior lateral-control observation in the same sourced alley; no attention label.",
                      "variable_assignments": {
                          "lateral_controller_profile": {"kind": "controller", "value": "steady" if kind == "steady_travel" else "variation"},
                          "observed_attention_state": {"kind": "subject_behavior", "value": None}},
                      "recording_description": recording_description(source["recording_description"]),
                      "unresolved_judgment_calls": [PHRASE],
                      "paired_probe_id": "alley_lateral_control_observation",
                      "deliberate_differences": ["lateral_controller_profile"],
                      "probe": {"primary_variable": "lateral_controller_profile",
                          "comparison_or_standard": "controlled exterior trajectory observation only",
                          "target_value_or_branch": kind}})
    case_stage = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": cases,
                  "sweep_specs": [{"sweep_id": "alley_attention_observation",
                      "target_law_id": LAW,
                      "judgment_refs": [{"phrase": PHRASE,
                          "note": "Exterior motion cannot determine interior attention."}],
                      "rationale": "No source-backed numerical interior-attention axis is available; exterior cases only compare requested lateral control.",
                      "status": "incomplete",
                      "missing_inputs": ["No justified interior-attention measurement or numeric judgment range is present in frozen sources; two exterior controller variants are observations only."]}],
                  "comparisons": plan["comparisons"],
                  "source_law_text": quote,
                  "source_assignment": "inputs/" + AID + "/assignment.json"}
    stages = {"relevance_batch": relevance, "relevance": relevance,
              "template": template, "judgment_observables": observables,
              "bindings": bindings, "cases": case_stage}
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "stages": {}}
    for name, value in stages.items():
        path = proposal_dir / (name + ".json")
        digest = write(path, value)
        reference = {"path": "proposals/" + path.name, "sha256": digest}
        index["stages"][name] = [reference] if name == "judgment_observables" else reference
    write(proposal_dir / "semantic-index.json", index)
    print("source-preserving semantic drafts: baseline plus two exact alley cases")


if __name__ == "__main__":
    build()
