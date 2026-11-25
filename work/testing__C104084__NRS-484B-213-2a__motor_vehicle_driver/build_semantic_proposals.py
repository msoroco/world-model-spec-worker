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
        {"name": "source_road_direction", "kind": "world_setup", "range_or_domain": ["two_way", "one_way"]},
    ]
    relevance = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": frozen_quote, "applies_to": [ACTOR],
                                    "relevance_type": "left-side driving near a crest with obstructed view and one-way exception",
                                    "confidence": "medium",
                                    "notes": "Source road direction, measured obstruction and hazard distance require independent original review."}],
                 "borderline_excluded": []}
    unresolved = ["Highway and road-direction authority", "Approaching a crest", "Obstructed view",
                  "Distance creating a hazard if an opposite-direction vehicle might approach"]
    judgments = [{"phrase": phrase, "note": "Original source review remains required; no legal threshold is inferred."}
                 for phrase in unresolved]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": frozen_quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Vehicle approaches a crest of grade or curve on a highway and driver view is obstructed within a hazard-creating distance.", "numeric_conditions": []},
                              "obligation": {"type": "must_not", "description": "Vehicle must not be driven to the left side of the highway during the stated condition.", "numeric_conditions": []},
                              "exceptions": [{"trigger": "Reviewed one-way highway designation",
                                  "effect": "Subsection 2 does not apply",
                                  "replacement_obligation": "No subsection 2 left-side prohibition inferred",
                                  "source_clause": "Subsection 2 does not apply upon a one-way highway."}],
                              "timing": {"description": "Join original body-side and crest-ray observations on the same approach frames.", "numeric_conditions": []},
                              "judgment_calls_needed": judgments},
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
                             "source_road_direction": {"kind": "world_setup", "value": direction}},
                         "recording_description": description(),
                         "paired_probe_id": AID + "__crest_branch_group",
                         "deliberate_differences": list(PAIR_VARIABLES.values()),
                         "probe": {"primary_variable": (
                             "requested_ego_side" if suffix in ("right_crest_obstructed", "left_crest_obstructed")
                             else "requested_crest_view" if suffix == "left_crest_clear"
                             else "source_road_direction"),
                             "comparison_or_standard": "Original source-bound same-frame crest context; no legal hazard cutoff",
                             "target_value_or_branch": suffix},
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
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared reviewed crest route reference before the exact left-side and one-way probes; source review pending.",
                "variable_assignments": proposed[0]["variable_assignments"],
                "recording_description": description(),
                "unresolved_judgment_calls": unresolved}
    sweeps = [{"sweep_id": f"c104084-judgment-{index}", "target_law_id": LAW,
               "judgment_refs": [item], "status": "incomplete",
               "rationale": "Original reviewed road, actor, camera and authority sources are required to bound a physical sweep.",
               "missing_inputs": ["Source-reviewed Native crest and highway designation",
                                  "Original driver-view and opposing-vehicle evidence"]}
              for index, item in enumerate(judgments, 1)]
    stage = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
             "cases": [baseline, *proposed], "comparisons": comparisons,
             "sweep_specs": sweeps, "sweeps_expanded": True}
    judgment_stages = []
    for item in judgments:
        channels = [{"name": name, "unit": "structured record", "description": "Original Native crest source join"}
                    for name in ("original_lane_directions", "crest_grade_profile",
                                 "ego_left_side_body_history", "opposing_vehicle_route_and_body",
                                 "driver_view_proxy_and_visibility", "highway_one_way_context",
                                 "frame_and_camera_join")]
        judgment_stages.append({"template_id": TEMPLATE_ID, "phrase": item["phrase"],
            "note": item["note"], "status": "draft",
            "observable_requirements": {"observables": channels, "context_inputs": [],
                "sweep_dimensions": [{"name": "source_reviewed_crest_visibility", "unit": "categorical",
                    "description": "Source-measured obstruction without a legal hazard cutoff"}],
                "landmarks": [], "recording_needs": channels,
                "limitations": ["Synthetic geometry and proxy rays do not establish original driver perception or legal hazard distance."]}})
    return {"relevance_batch": relevance, "relevance": relevance,
            "template": template, "judgment_observables": judgment_stages,
            "bindings": bindings, "cases": stage}


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
        if name == "judgment_observables":
            refs[name] = []
            for index, judgment in enumerate(payload, 1):
                path = destination / f"judgment-{index}.json"
                path.write_text(json.dumps(judgment, indent=2, ensure_ascii=False) + "\n")
                refs[name].append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
            continue
        path = destination / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "status": "draft", "physical_acceptance": "unverified",
             "source": {"path": str(assignment_path.relative_to(PROJECT)), "sha256": sha(assignment_path)},
             "sources": [{"path": str(p.relative_to(PROJECT)), "sha256": sha(p)}
                         for p in (assignment_path, plan_path, coverage_path)], "stages": refs}
    (destination / "semantic-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print("four exact crest semantic cases and three isolated comparisons bound to frozen law")


if __name__ == "__main__":
    main()
