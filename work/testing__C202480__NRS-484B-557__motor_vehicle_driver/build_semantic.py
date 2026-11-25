"""Author source-faithful draft semantic stages for the exact rail-stop matrix."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / "proposals"
LAW = "NRS-484B-557"
ACTOR = "motor_vehicle_driver"
PHRASE = "exercising due care"
NOTE = "Original approach conflict, visibility and feasible departure alternatives require independent review; no legal due-care cutoff is chosen."


def save(name: str, value: dict) -> dict:
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / (name + ".json")
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    assignment = json.loads((HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_text())
    description = json.loads((HERE / "config.json").read_text())["recording_description"]
    quote = assignment["law"]["text"]
    relevance = {"cell_id": plan["cell_id"], "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR],
                                    "relevance_type": "direct designated highway railroad grade-crossing stop duty",
                                    "confidence": "high",
                                    "notes": "Original DOT designation, governing official sign and rail survey remain source-gated."}],
                 "borderline_excluded": []}
    template_id = LAW + "@" + ACTOR
    parameters = [
        ("planned_stop_body_gap_ft", "world_setup", "requested gap in feet; original body gap is separately observed"),
        ("stop_behavior", "controller", "complete cessation request or rolling passage"),
        ("departure_context", "world_setup", "clear approach or reviewed crossing-conflict actor"),
        ("original_body_gap_ft", "subject_behavior", "original four-corner body interval to nearest rail, feet"),
        ("complete_stop_observed", "subject_behavior", "zero original speed after approach and before track contact"),
        ("conflict_actor_presence", "subject_behavior", "original second actor body and frame history")]
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
                "quote": quote,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "DOT or DOT-approved local designation of a highway railroad grade crossing with an official stop sign governing this approach.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "The driver stops within 50 feet but not less than 15 feet from the nearest track, then proceeds only upon exercising due care.",
                                   "type": "must",
                                   "numeric_conditions": [
                                       {"variable": "original_body_gap_ft", "operator": ">=", "value": 15, "unit": "ft"},
                                       {"variable": "original_body_gap_ft", "operator": "<=", "value": 50, "unit": "ft"}]},
                    "exceptions": [],
                    "timing": {"description": "Complete cessation precedes any subsequent proceeding at the designated crossing.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in parameters]}
    judgment = {"template_id": template_id, "phrase": PHRASE, "note": NOTE,
                "status": "draft", "observable_requirements": {
                    "observables": [{"name": "crossing_conflict_history", "unit": "structured",
                                     "description": "Retain original actor footprints, speeds, scene timing and absence/presence."}],
                    "context_inputs": [{"name": "crossing_authority", "unit": "metadata",
                                        "description": "Retain original designation, governing sign and rail geometry sources."}],
                    "sweep_dimensions": [], "landmarks": [],
                    "recording_needs": [{"name": "crossing_conflict_history", "unit": "structured",
                                         "description": "Original crossing-approach conflict body history for later due-care review."}],
                    "limitations": ["Conflict geometry and synthetic sampling cannot define legal due care."]}}
    bindings = {"cell_id": plan["cell_id"], "actor": ACTOR, "status": "draft",
                "established_contexts": ["Frozen C202480 rail-crossing stop-sign motor-vehicle-driver cell; original DOT designation and sign governance remain source-gated."],
                "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{"name": name, "kind": kind,
                                         "range_or_domain": domain, "used_by_laws": [LAW]}
                                        for name, kind, domain in parameters]}
    def assignments(case):
        values = {"planned_stop_body_gap_ft": case["planned_stop_body_gap_ft"],
                  "stop_behavior": case["stop_behavior"],
                  "departure_context": case["departure_context"],
                  "original_body_gap_ft": None, "complete_stop_observed": None,
                  "conflict_actor_presence": None}
        return {name: {"kind": kind, "value": values[name]}
                for name, kind, _ in parameters}
    baseline = {"case_id": HERE.name + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "unselected fixed source context for exact comparisons",
                "variable_assignments": assignments(plan["cases"][-1]),
                "unresolved_judgment_calls": [PHRASE],
                "recording_description": description}
    cases = [baseline]
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(HERE.name + "__")
        if suffix in ("inside_15", "at_15", "above_15"):
            pair, index, threshold, operator, variable = "lower_15_ft", 0, 15, ">=", "planned_stop_body_gap_ft"
        elif suffix in ("below_50", "at_50", "above_50"):
            pair, index, threshold, operator, variable = "upper_50_ft", 1, 50, "<=", "planned_stop_body_gap_ft"
        elif suffix == "rolling":
            pair, index, threshold, operator, variable = "cessation", None, None, None, "stop_behavior"
        elif suffix == "depart_conflict":
            pair, index, threshold, operator, variable = "subsequent_care", None, None, None, "departure_context"
        else:
            pair, index, threshold, operator, variable = "cessation", None, None, None, "stop_behavior"
        probe = {"primary_variable": variable,
                 "comparison_or_standard": pair + "; actual original evidence measured later",
                 "target_value_or_branch": case[variable if variable in case else "planned_stop_body_gap_ft"]}
        row = {"case_id": case["case_id"], "target_law_id": LAW,
               "target_type": "boundary_probe", "status": "draft",
               "rationale": case["purpose"] + "; no anticipated legal result",
               "variable_assignments": assignments(case),
               "unresolved_judgment_calls": [PHRASE],
               "recording_description": description,
               "paired_probe_id": pair, "deliberate_differences": [variable],
               "probe": probe}
        if index is not None:
            probe.update({"threshold_ref": f"obligation.numeric_conditions[{index}]",
                          "operator": operator, "unit": "ft",
                          "test_value": case["planned_stop_body_gap_ft"]})
            row["epsilon_used"] = {"value": 0.1, "unit": "ft",
                                   "rationale": "Engineering probe separation, not a legal tolerance."}
        cases.append(row)
    case_stage = {"cell_id": plan["cell_id"], "actor": ACTOR, "status": "draft",
                  "cases": cases, "sweep_specs": [{"sweep_id": "due_care_scene_sweep",
                     "target_law_id": LAW, "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                     "rationale": "Original due-care scene sweep needs source-reviewed rail-traffic timing and feasible Native actor controls.",
                     "status": "incomplete",
                     "missing_inputs": ["Source-reviewed rail traffic route, phase timing and feasible independent conflict range are absent from the frozen assignment."]}],
                  "sweeps_expanded": True}
    references = {"relevance_batch": save("relevance_batch", relevance),
                  "relevance": save("relevance", relevance),
                  "template": save("template", template),
                  "judgment_observables": [save("judgment-due-care", judgment)],
                  "bindings": save("bindings", bindings),
                  "cases": save("cases", case_stage)}
    save("semantic-index", {"format": "worker-semantic-delivery",
                            "assignment_id": HERE.name, "stages": references})
    print(json.dumps({"assignment_id": HERE.name, "selected_cases": len(cases) - 1,
                      "judgment_sweep": "incomplete pending source-reviewed range"}))


if __name__ == "__main__":
    main()
