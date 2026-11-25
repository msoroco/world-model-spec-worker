"""Build source-bound draft semantic stages for six exact sight-speed cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
AID = ROOT.name
LAW = "LVMC-11-16-040"
ACTOR = "motor_vehicle_driver"
EXPECTED = {
    "blocked_below": (14, "west_building", False, False),
    "blocked_at": (15, "west_building", False, False),
    "blocked_above": (16, "west_building", False, False),
    "clear_at": (15, None, False, False),
    "through_blocked": (15, "west_building", True, False),
    "controlled_blocked": (15, "west_building", False, True),
}
VARS = ("requested_traversal_speed_mph", "requested_occluder",
        "through_designation", "traffic_controlled_intersection")
PAIR_VARIABLE = dict(zip(("speed_boundary", "sight_condition", "through_exception", "control_exception"), VARS))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(assignment: dict, plan: dict, quote: str) -> dict:
    if (assignment["assignment_id"], assignment["law_id"], assignment["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Frozen assignment identity mismatch")
    if (plan["assignment_id"], plan["law_id"], plan["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Case-plan identity mismatch")
    if plan["law_text"] != quote:
        raise ValueError("Case-plan quote differs from frozen exact law")
    cases = {row["case_id"].removeprefix(AID + "__"): row for row in plan["cases"]}
    if set(cases) != set(EXPECTED) or len(plan["cases"]) != 6:
        raise ValueError("Six exact sight-speed cases required")
    parameters = [
        {"name": VARS[0], "kind": "controller", "range_or_domain": [14, 15, 16]},
        {"name": VARS[1], "kind": "world_setup", "range_or_domain": [None, "west_building"]},
        {"name": VARS[2], "kind": "world_setup", "range_or_domain": [False, True]},
        {"name": VARS[3], "kind": "world_setup", "range_or_domain": [False, True]},
    ]
    unresolved = ["Municipal jurisdiction and qualifying street intersection",
                  "Original all-entering-arm 100-foot sight evidence",
                  "Actual traversal speed and view", "Source through-street or traffic-control designation"]
    relevance = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "confidence": "medium", "relevance_type": "conditional 15 mph prima facie traversal speed",
                                    "notes": "Original approach-view, all entering arms, traversal and exception sources need independent review."}],
                 "borderline_excluded": []}
    template = {"template_id": f"{LAW}@{ACTOR}", "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "During the last 100 feet of approach, the driver lacks a clear unobstructed view of the intersection and traffic on every entering street/highway for 100 feet.", "numeric_conditions": []},
                              "obligation": {"type": "must", "description": "The exact text gives a fifteen-mile-per-hour prima facie traversal value under the sight condition; no legal verdict follows from the probe.", "numeric_conditions": [{"variable": "traversal_speed_mph", "operator": "<=", "value": 15, "unit": "mph"}]},
                              "exceptions": [{"trigger": "Reviewed through street or highway designation", "effect": "This fifteen-mile-per-hour prima facie clause is excepted.", "replacement_obligation": "No replacement obligation is asserted from this clause.", "source_clause": "except on a through street or highway"},
                                             {"trigger": "Reviewed traffic-controlled intersection inventory", "effect": "This fifteen-mile-per-hour prima facie clause is excepted.", "replacement_obligation": "No replacement obligation is asserted from this clause.", "source_clause": "or at a traffic-controlled intersection"}],
                              "timing": {"description": "Observe approach sight during the final 100 feet and speed during traversal as separate intervals.", "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": "Requires reviewed original Native and municipal sources."} for phrase in unresolved]},
                "parameter_refs": parameters}
    bindings = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                "established_contexts": ["C111278 intersection traversal; map and authority source pending"],
                "law_refs": [{"template_id": template["template_id"], "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{**p, "used_by_laws": [LAW]} for p in parameters]}
    proposed = []
    for suffix, values in EXPECTED.items():
        row = cases[suffix]
        if (row["case_id"] != AID + "__" + suffix or row["target_law_id"] != LAW or
                row["physical_status"] != "unverified" or tuple(row[name] for name in VARS) != values):
            raise ValueError(f"Exact sight-speed case variables changed: {suffix}")
        proposed.append({"case_id": row["case_id"], "target_law_id": LAW,
                         "target_type": "boundary_probe", "status": "draft",
                         "rationale": "Requested speed, occluder and exception context are not original measurements or legal findings.",
                         "variable_assignments": {name: {"kind": parameter["kind"], "value": value}
                                                  for name, parameter, value in zip(VARS, parameters, values)},
                         "recording_description": row["recording_description"],
                         "unresolved_judgment_calls": unresolved,
                         "paired_probe_id": "c111278-" + ("speed_boundary" if suffix.startswith("blocked_") else suffix),
                         "deliberate_differences": ["requested_traversal_speed_mph" if suffix.startswith("blocked_") else
                                                    "requested_occluder" if suffix == "clear_at" else
                                                    "through_designation" if suffix == "through_blocked" else
                                                    "traffic_controlled_intersection"],
                         "probe": {"primary_variable": "requested_traversal_speed_mph" if suffix.startswith("blocked_") else
                                                    "requested_occluder" if suffix == "clear_at" else
                                                    "through_designation" if suffix == "through_blocked" else
                                                    "traffic_controlled_intersection",
                                   "comparison_or_standard": "same-site blocked-at reference and exact LVMC clause",
                                   "target_value_or_branch": suffix,
                                   **({"threshold_ref": "obligation.numeric_conditions[0]", "operator": "<=", "unit": "mph",
                                       "test_value": row["requested_traversal_speed_mph"]} if suffix.startswith("blocked_") else {})},
                         **({"epsilon_used": {"value": 1, "unit": "mph", "rationale": "Physical probe spacing; no legal tolerance."}}
                            if suffix.startswith("blocked_") else {})})
    by_id = {row["case_id"]: row["variable_assignments"] for row in proposed}
    if {row["comparison_id"] for row in plan["comparisons"]} != set(PAIR_VARIABLE):
        raise ValueError("Comparison inventory changed")
    comparisons = []
    for row in plan["comparisons"]:
        ids = row["case_ids"]
        if len(ids) < 2 or any(case not in by_id for case in ids):
            raise ValueError("Comparison exact cases changed")
        changed = {name for name in VARS if len({json.dumps(by_id[case][name], sort_keys=True) for case in ids}) > 1}
        if changed != {PAIR_VARIABLE[row["comparison_id"]]}:
            raise ValueError("Controlled comparison variables changed")
        comparisons.append({"comparison_id": row["comparison_id"], "case_ids": ids,
                            "fixed_conditions": row["fixed_conditions"],
                            "changed_variable": next(iter(changed)),
                            "deliberate_differences": row["deliberate_differences"]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared C111278 comparison reference; no delivery recording.",
                "variable_assignments": proposed[1]["variable_assignments"],
                "recording_description": proposed[1]["recording_description"],
                "unresolved_judgment_calls": unresolved}
    case_stage = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                  "cases": [baseline] + proposed, "comparisons": comparisons,
                  "sweep_specs": [{"sweep_id": f"c111278-source-review-{index}",
                                   "target_law_id": LAW,
                                   "judgment_refs": [{"phrase": phrase,
                                                      "note": "Requires reviewed original Native and municipal sources."}],
                                   "status": "incomplete",
                                   "rationale": "Original physical and municipal evidence must bound this judgment before a sweep can be specified.",
                                   "missing_inputs": ["Reviewed source-bound Native capture and municipal site authority"]}
                                  for index, phrase in enumerate(unresolved, 1)],
                  "sweeps_expanded": True}
    named = lambda name, description: {"name": name, "unit": "structured record", "description": description}
    observables = [named(o["name"], o["description"]) for o in plan["observations"]]
    contexts = [named("municipal_site_context", "Cited jurisdiction, road, arms, boundary and exception inventory")]
    judgment = [{"template_id": template["template_id"], "phrase": phrase,
                 "note": "Requires reviewed original Native and municipal sources.", "status": "draft",
                 "observable_requirements": {"observables": observables, "context_inputs": contexts,
                    "sweep_dimensions": [], "landmarks": [], "recording_needs": observables,
                    "limitations": ["No legal visibility or speed verdict is inferred from the engineering observation."]}}
                for phrase in unresolved]
    return {"relevance_batch": relevance, "relevance": relevance,
            "template": template, "judgment_observables": judgment,
            "bindings": bindings, "cases": case_stage}


def main() -> None:
    assignment_path = PROJECT / "inputs" / AID / "assignment.json"
    plan_path = ROOT / "case-plan.json"
    coverage_path = PROJECT / "inputs" / "coverage" / "branch-sources.json"
    quote = json.loads(coverage_path.read_text())["laws"][LAW]["law"]["text"]
    stages = prepare(json.loads(assignment_path.read_text()), json.loads(plan_path.read_text()), quote)
    destination = ROOT / "proposals"
    destination.mkdir(exist_ok=True)
    refs = {}
    for name, payload in stages.items():
        if name == "judgment_observables":
            continue
        path = destination / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
    refs["judgment_observables"] = []
    for index, payload in enumerate(stages["judgment_observables"], 1):
        path = destination / f"judgment-{index}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs["judgment_observables"].append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "status": "draft", "physical_acceptance": "unverified",
             "sources": [{"path": str(path.relative_to(PROJECT)), "sha256": sha(path)}
                         for path in (assignment_path, plan_path, coverage_path)], "stages": refs}
    (destination / "semantic-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print("six exact sight-speed semantic cases and four isolated comparisons")


if __name__ == "__main__":
    main()
