"""Build draft source-bound semantic stages for exact crest-view comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from build_constructions import description

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-484B-213-2a"
ACTOR = "motor_vehicle_driver"
TEMPLATE_ID = f"{LAW}@{ACTOR}"
VALUES = {
    "right_crest_obstructed": ("reference_corner", "obstructed", "two_way"),
    "left_crest_obstructed": ("approach", "obstructed", "two_way"),
    "left_crest_clear": ("approach", "clear", "two_way"),
    "left_one_way_obstructed": ("approach", "obstructed", "one_way"),
}
PAIR_VARIABLES = {"left_side_motion": "requested_ego_side",
                  "crest_view_obstruction": "requested_crest_view",
                  "one_way_exception": "source_road_direction"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(assignment: dict, plan: dict, frozen_quote: str) -> dict:
    if (assignment["assignment_id"], assignment["law_id"], assignment["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Frozen assignment identity mismatch")
    if (plan["assignment_id"], plan["law_id"], plan["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Case plan identity mismatch")
    if plan["law_text"] != frozen_quote:
        raise ValueError("Case plan differs from frozen exact law text")
    cases = {case["case_id"].removeprefix(AID + "__"): case for case in plan["cases"]}
    if set(cases) != set(VALUES) or len(plan["cases"]) != 4:
        raise ValueError("Four exact crest cases required")
    params = [
        {"name": "requested_ego_side", "kind": "controller", "range_or_domain": ["reference_corner", "approach"]},
        {"name": "requested_crest_view", "kind": "world_setup", "range_or_domain": ["obstructed", "clear"]},
        {"name": "source_road_direction", "kind": "source_context", "range_or_domain": ["two_way", "one_way"]},
    ]
    relevance = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": frozen_quote, "applies_to": [ACTOR],
                                    "relevance_type": "left-side driving near a crest with obstructed view and one-way exception",
                                    "confidence": "medium",
                                    "notes": "Source road direction, measured obstruction and hazard distance require independent original review."}],
                 "borderline_excluded": []}
    unresolved = ["Highway and road-direction authority", "Approaching a crest", "Obstructed view",
                  "Distance creating a hazard if an opposite-direction vehicle might approach"]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": frozen_quote,
                "structure": {"activation": {"condition": "Vehicle approaches a crest of grade or curve on a highway and driver view is obstructed within a hazard-creating distance."},
                              "obligation": {"type": "prohibition", "description": "Vehicle must not be driven to the left side of the highway during the stated condition."},
                              "exceptions": ["Subsection 2 does not apply upon a one-way highway."],
                              "timing": {"description": "Join original body-side and crest-ray observations on the same approach frames."},
                              "judgment_calls_needed": unresolved},
                "parameter_refs": params}
    bindings = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                "established_contexts": ["C104084 grade approach with source-reviewed highway direction pending"],
                "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{**p, "used_by_laws": [LAW]} for p in params]}
    proposed = []
    for suffix, (side, view, direction) in VALUES.items():
        case = cases[suffix]
        if case["case_id"] != AID + "__" + suffix or case["target_law_id"] != LAW or case.get("physical_status", "unverified") != "unverified":
            raise ValueError("Exact case identity or physical status changed")
        proposed.append({"case_id": case["case_id"], "target_law_id": LAW,
                         "target_type": "boundary_probe", "status": "draft",
                         "rationale": case["purpose"] + " Requested context is not original observed road or view state.",
                         "variable_assignments": {
                             "requested_ego_side": {"kind": "controller", "value": side},
                             "requested_crest_view": {"kind": "world_setup", "value": view},
                             "source_road_direction": {"kind": "source_context", "value": direction}},
                         "recording_description": description(),
                         "unresolved_judgment_calls": unresolved})
    by_id = {c["case_id"]: c["variable_assignments"] for c in proposed}
    comparisons = []
    if {c["comparison_id"] for c in plan["comparisons"]} != set(PAIR_VARIABLES):
        raise ValueError("Comparison inventory changed")
    for comparison in plan["comparisons"]:
        ids = comparison["case_ids"]
        if len(ids) != 2 or any(x not in by_id for x in ids):
            raise ValueError("Comparison exact-case membership changed")
        changed = {name for name in by_id[ids[0]] if by_id[ids[0]][name] != by_id[ids[1]][name]}
        if changed != {PAIR_VARIABLES[comparison["comparison_id"]]}:
            raise ValueError("Comparison variable isolation changed")
        comparisons.append({"comparison_id": comparison["comparison_id"], "case_ids": ids,
                            "fixed_conditions": comparison["fixed_conditions"],
                            "changed_variable": next(iter(changed)),
                            "deliberate_differences": comparison["deliberate_differences"]})
    stage = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
             "cases": proposed, "comparisons": comparisons, "sweep_specs": []}
    return {"relevance_batch": relevance, "relevance": relevance,
            "template": template, "bindings": bindings, "cases": stage}


def main() -> None:
    assignment_path = PROJECT / "inputs" / AID / "assignment.json"
    plan_path = ROOT / "case-plan.json"
    coverage_path = PROJECT / "inputs" / "coverage" / "branch-sources.json"
    frozen = json.loads(coverage_path.read_text())["laws"][LAW]["law"]["text"]
    stages = prepare(json.loads(assignment_path.read_text()), json.loads(plan_path.read_text()), frozen)
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
             "sources": [{"path": str(p.relative_to(PROJECT)), "sha256": sha(p)}
                         for p in (assignment_path, plan_path, coverage_path)], "stages": refs}
    (destination / "semantic-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print("four exact crest semantic cases and three isolated comparisons bound to frozen law")


if __name__ == "__main__":
    main()
