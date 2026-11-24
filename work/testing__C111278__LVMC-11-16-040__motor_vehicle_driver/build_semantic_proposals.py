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
        {"name": VARS[2], "kind": "source_context", "range_or_domain": [False, True]},
        {"name": VARS[3], "kind": "source_context", "range_or_domain": [False, True]},
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
                "structure": {"activation": {"condition": "During the last 100 feet of approach, the driver lacks a clear unobstructed view of the intersection and traffic on every entering street/highway for 100 feet."},
                              "obligation": {"type": "prima_facie_speed_limit", "description": "Fifteen miles per hour when traversing the intersection under that condition."},
                              "exceptions": ["Through street or highway", "Traffic-controlled intersection"],
                              "timing": {"description": "Observe approach sight during the final 100 feet and speed during traversal as separate intervals."},
                              "judgment_calls_needed": unresolved},
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
                         "unresolved_judgment_calls": unresolved})
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
    case_stage = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                  "cases": proposed, "comparisons": comparisons, "sweep_specs": []}
    return {"relevance_batch": relevance, "relevance": relevance,
            "template": template, "bindings": bindings, "cases": case_stage}


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
        path = destination / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
    refs["judgment_observables"] = []
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "status": "draft", "physical_acceptance": "unverified",
             "sources": [{"path": str(path.relative_to(PROJECT)), "sha256": sha(path)}
                         for path in (assignment_path, plan_path, coverage_path)], "stages": refs}
    (destination / "semantic-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print("six exact sight-speed semantic cases and four isolated comparisons")


if __name__ == "__main__":
    main()
