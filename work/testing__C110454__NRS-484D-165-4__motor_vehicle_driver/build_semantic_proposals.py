"""Build source-bound draft semantic stages for parked-vehicle headlamps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-484D-165-4"
ACTOR = "motor_vehicle_driver"
MODES = {"unlit", "low_beam", "high_beam"}
PAIRS = {"lighted_applicability": ("unlit", "low_beam"),
         "dimmed_vs_bright_headlamp": ("low_beam", "high_beam")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(assignment: dict, plan: dict, frozen_quote: str) -> dict:
    if (assignment["assignment_id"], assignment["law_id"], assignment["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Frozen assignment identity mismatch")
    if (plan["assignment_id"], plan["law_id"], plan["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Case-plan identity mismatch")
    if plan["law_text"] != frozen_quote:
        raise ValueError("Case-plan quote differs from frozen law")
    cases = {row["case_id"].removeprefix(AID + "__"): row for row in plan["cases"]}
    if set(cases) != MODES or len(plan["cases"]) != 3:
        raise ValueError("Three exact headlamp cases required")
    parameter = {"name": "requested_headlamp_mode", "kind": "controller",
                 "range_or_domain": sorted(MODES)}
    judgments = [
        {"phrase": "parked vehicle", "note": "Parking requires original body and site observations."},
        {"phrase": "lighted headlamps", "note": "API bits alone do not show emitted light."},
        {"phrase": "depressed or dimmed", "note": "Original beam and independent physical review remain required."},
    ]
    unresolved = [item['phrase'] for item in judgments]
    relevance = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": frozen_quote,
                                    "applies_to": [ACTOR], "confidence": "medium",
                                    "relevance_type": "parked-vehicle lighted-headlamp dimming requirement",
                                    "notes": "Original parking, device state, emission and aim need independent source review."}],
                 "borderline_excluded": []}
    template = {"template_id": f"{LAW}@{ACTOR}", "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": frozen_quote,
                "structure": {"activation": {"condition": "A vehicle is parked and its headlamps are actually lighted."},
                              "obligation": {"type": "requirement", "description": "Any lighted headlamps upon the parked vehicle shall be depressed or dimmed."},
                              "exceptions": [],
                              "timing": {"description": "Join original parked-body, lamp-state and source image observations on the same frames."},
                              "judgment_calls_needed": judgments},
                "parameter_refs": [parameter]}
    bindings = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                "established_contexts": ["C110454 intersection parking footprint pending site review"],
                "law_refs": [{"template_id": template["template_id"], "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{**parameter, "used_by_laws": [LAW]}]}
    proposed = []
    for mode in ("unlit", "low_beam", "high_beam"):
        row = cases[mode]
        if (row["case_id"] != AID + "__" + mode or row["target_law_id"] != LAW or
                row["requested_headlamp_mode"] != mode or row["physical_status"] != "unverified"):
            raise ValueError("Exact headlamp case variables changed")
        construction = ROOT / f"construction-{mode}.json"
        if not construction.is_file() or json.loads(construction.read_text())["case_id"] != row["case_id"]:
            raise ValueError("Exact diagnostic construction missing")
        proposed.append({"case_id": row["case_id"], "target_law_id": LAW,
                         "target_type": "boundary_probe", "status": "draft",
                         "rationale": row["review_note"],
                         "variable_assignments": {"requested_headlamp_mode": {"kind": "controller", "value": mode}},
                         "recording_description": json.loads(construction.read_text())["recording_description"],
                         "diagnostic_construction": {"path": construction.name, "sha256": sha(construction)},
                         "unresolved_judgment_calls": unresolved,
                         "paired_probe_id": AID + '__' + mode + '_comparison',
                         "deliberate_differences": ["requested_headlamp_mode"],
                         "probe": {"primary_variable": "requested_headlamp_mode",
                                   "comparison_or_standard": "Source-matched parked headlamp-mode comparison; no legal cutoff",
                                   "target_value_or_branch": mode}})
    exact = {row["case_id"]: row for row in proposed}
    if {row["comparison_id"] for row in plan["comparisons"]} != set(PAIRS):
        raise ValueError("Comparison inventory changed")
    comparisons = []
    for pair in plan["comparisons"]:
        modes = PAIRS[pair["comparison_id"]]
        ids = [AID + "__" + mode for mode in modes]
        if pair["case_ids"] != ids or any(case not in exact for case in ids):
            raise ValueError("Exact comparison membership changed")
        if exact[ids[0]]["variable_assignments"]["requested_headlamp_mode"] == exact[ids[1]]["variable_assignments"]["requested_headlamp_mode"]:
            raise ValueError("Comparison does not change requested lamp mode")
        comparisons.append({"comparison_id": pair["comparison_id"], "case_ids": ids,
                            "fixed_conditions": pair["fixed_conditions"],
                            "changed_variable": "requested_headlamp_mode",
                            "deliberate_differences": pair["deliberate_differences"]})
    baseline = {"case_id": AID + '__baseline', "target_law_id": None,
                "target_type": "baseline", "rationale": "Shared parked intersection setup before requested mode varies.",
                "variable_assignments": {"requested_headlamp_mode": {"kind": "controller", "value": "unlit"}},
                "recording_description": proposed[0]['recording_description'],
                "unresolved_judgment_calls": unresolved}
    sweep_specs = [{"sweep_id": AID + '__judgment_' + str(index),
                    "target_law_id": LAW, "judgment_refs": [item],
                    "status": "incomplete",
                    "rationale": "Original Native source review is required before physical judgment sweep bounds can be chosen.",
                    "missing_inputs": ["Reviewed original parked-body, lamp pixel and beam source"]}
                   for index, item in enumerate(judgments, 1)]
    stage = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
             "cases": [baseline] + proposed, "comparisons": comparisons,
             "sweep_specs": sweep_specs, "sweeps_expanded": True}
    return {"relevance_batch": relevance, "relevance": relevance,
            "template": template, "bindings": bindings, "cases": stage,
            "judgments": judgments}


def main() -> None:
    assignment_path = PROJECT / "inputs" / AID / "assignment.json"
    plan_path = ROOT / "case-plan.json"
    coverage_path = PROJECT / "inputs" / "coverage" / "branch-sources.json"
    frozen_quote = json.loads(coverage_path.read_text())["laws"][LAW]["law"]["text"]
    stages = prepare(json.loads(assignment_path.read_text()), json.loads(plan_path.read_text()), frozen_quote)
    destination = ROOT / "proposals"
    destination.mkdir(exist_ok=True)
    refs = {}
    for name, payload in stages.items():
        if name == 'judgments':
            continue
        path = destination / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
    refs["judgment_observables"] = []
    for index, judgment in enumerate(stages['judgments'], 1):
        phrase = judgment['phrase']
        channel = 'original_actor_state' if phrase == 'parked vehicle' else 'headlamp_emission_and_aim_review'
        requirement = {"name": channel, "unit": "structured record",
                       "description": "Original source-joined physical observation for " + phrase}
        payload = {"template_id": stages['template']['template_id'],
                   "phrase": phrase, "note": judgment['note'], "status": "draft",
                   "observable_requirements": {"observables": [requirement],
                       "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                       "recording_needs": [requirement],
                       "limitations": ["Original Native sources require independent physical review; no legal verdict is inferred."]}}
        path = destination / f"judgment-{index}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs['judgment_observables'].append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "status": "draft", "physical_acceptance": "unverified",
             "sources": [{"path": str(path.relative_to(PROJECT)), "sha256": sha(path)}
                         for path in (assignment_path, plan_path, coverage_path)], "stages": refs}
    (destination / "semantic-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print("three exact headlamp semantic cases and two controlled comparisons")


if __name__ == "__main__":
    main()
