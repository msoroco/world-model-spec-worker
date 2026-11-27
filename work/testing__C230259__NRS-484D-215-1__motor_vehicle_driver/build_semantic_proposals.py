"""Draft canonical stages for the exact moving-road lighting law."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
LAW = "NRS-484D-215-1"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR


def _hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(folder: Path, name: str, value: dict):
    path = folder / (name + ".json")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + path.name, "sha256": _hash(path)}


def build():
    frozen_path = REPO / "inputs" / ASSIGNMENT / "assignment.json"
    frozen = json.loads(frozen_path.read_text())
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if (frozen["assignment_id"] != ASSIGNMENT or frozen["law_id"] != LAW or
            frozen["law"]["text"] != plan["law_text"] or
            len(plan["cases"]) != 8 or len(plan["comparisons"]) != 6):
        raise ValueError("frozen moving-beam law/case plan differs")
    quote = frozen["law"]["text"]
    parameters = [
        {"name": "requested_beam", "kind": "controller", "range_or_domain": ["off", "low", "high"]},
        {"name": "requested_start_body_gap_ft", "kind": "world_setup", "range_or_domain": [499, 500, 501, 1400]},
        {"name": "requested_contour", "kind": "world_setup", "range_or_domain": ["level", "crest"]},
        {"name": "requested_load", "kind": "world_setup", "range_or_domain": ["standard", "loaded"]},
    ]
    judgments = [
        {"phrase": "safe distance", "note": "No numeric safe-distance cutoff is supplied; measure person/vehicle visibility and original beam pixels."},
        {"phrase": "glaring rays are not projected into the eyes", "note": "Original oncoming driver-eye projection and calibrated beam review remain required."},
        {"phrase": "lowermost distribution of light", "note": "CARLA low-beam bits do not certify the NRS 484D.210(2) equipment specification."},
    ]
    relevance = {"cell_id": "C230259", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR], "confidence": "medium",
                                    "relevance_type": "moving highway beam and oncoming glare",
                                    "notes": "Exact time, road, original beam/eye and lowermost equipment sources require local review."}],
                 "borderline_excluded": []}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote,
                "structure": {
                    "activation": {"condition": "A motor vehicle is operated on the traveled highway or adjacent shoulder during NRS 484D.100 times."},
                    "obligation": {"type": "requirement",
                                   "description": "Use a distribution revealing persons and vehicles a safe distance ahead; when approaching an oncoming vehicle within 500 feet, avoid glaring rays in the driver's eyes.",
                                   "numeric_conditions": [{"variable": "oncoming_body_gap_m", "operator": "<=", "value": 152.4, "unit": "m"}]},
                    "exceptions": [{"trigger": "lowermost distribution specified by NRS 484D.210(2)",
                                    "effect": "deemed to avoid glare regardless of contour and loading",
                                    "replacement_obligation": "Retain independent source review of the actual lowermost distribution.",
                                    "source_clause": "The lowermost distribution of light, or composite beam, specified in subsection 2 of NRS 484D.210 [DEF-NRS-484D-210-1-2] shall be deemed to avoid glare at all times, regardless of road contour and loading."}],
                    "timing": {"description": "Join actual oncoming body/eye gap, beam readback, frame-specific pixels and NRS 484D.100 applicability on original 20 Hz frames."},
                    "judgment_calls_needed": judgments},
                "parameter_refs": parameters}
    bindings = {"cell_id": "C230259", "actor": ACTOR, "status": "draft",
                "established_contexts": ["C230259 source-reviewed Nevada road with opposite-moving motor vehicle; time and highway sources pending local review"],
                "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
                "context_refs": [],
                "fixed_parameters": [{"name": "nevada_highway_and_lighting_time", "kind": "world_setup",
                                      "value": "reviewed original source packet"}],
                "variable_parameters": [{**p, "used_by_laws": [LAW]} for p in parameters]}
    description = json.loads((ROOT / "construction.json").read_text())["recording_description"]
    unresolved = [j["phrase"] for j in judgments]
    selected = []
    for case in plan["cases"]:
        suffix = case["case_id"].split("__")[-1]
        construction = ROOT / "cases" / suffix / "construction.json"
        if not construction.is_file():
            raise ValueError("exact construction missing: " + suffix)
        assignments = {name: {"kind": kind, "value": case[source]}
                       for name, kind, source in (
                           ("requested_beam", "controller", "requested_beam"),
                           ("requested_start_body_gap_ft", "world_setup", "requested_start_body_gap_ft"),
                           ("requested_contour", "world_setup", "requested_contour"),
                           ("requested_load", "world_setup", "requested_load"))}
        primary = "requested_beam"
        differences = [primary]
        paired = ASSIGNMENT + "__" + suffix
        if suffix in ("oncoming_499_low", "oncoming_500_low", "oncoming_501_low"):
            primary = "requested_start_body_gap_ft"
            differences = [primary]
            paired = ASSIGNMENT + "__500ft_body_gap"
        elif suffix == "oncoming_499_low_crest_loaded":
            primary = "requested_contour"
            differences = ["requested_contour", "requested_load"]
        probe = {"primary_variable": primary,
                 "comparison_or_standard": "Original source comparison; no legal beam or glare outcome implied",
                 "target_value_or_branch": suffix}
        proposed = {"case_id": case["case_id"], "target_law_id": LAW,
                    "target_type": "boundary_probe", "status": "draft",
                    "rationale": "Source-bound exact beam, oncoming distance, contour and loading probe; actual physical outcome unverified.",
                    "variable_assignments": assignments,
                    "recording_description": description,
                    "diagnostic_construction": {"path": str(construction.relative_to(ROOT)),
                                                "sha256": _hash(construction)},
                    "unresolved_judgment_calls": unresolved,
                    "paired_probe_id": paired,
                    "deliberate_differences": differences,
                    "probe": probe}
        if suffix in ("oncoming_499_low", "oncoming_500_low", "oncoming_501_low"):
            proposed["probe"].update({"threshold_ref": "obligation.numeric_conditions[0]",
                                       "operator": "<=", "unit": "m",
                                       "test_value": case["requested_start_body_gap_ft"] * .3048})
            proposed["epsilon_used"] = .3048
        selected.append(proposed)
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Common source-reviewed road, time, actor and camera setup before beam and distance variables change.",
                "variable_assignments": {"requested_beam": {"kind": "controller", "value": "low"},
                                         "requested_start_body_gap_ft": {"kind": "world_setup", "value": 1400},
                                         "requested_contour": {"kind": "world_setup", "value": "level"},
                                         "requested_load": {"kind": "world_setup", "value": "standard"}},
                "recording_description": description,
                "unresolved_judgment_calls": unresolved}
    sweeps = [{"sweep_id": ASSIGNMENT + "__judgment_" + str(index),
               "target_law_id": LAW, "judgment_refs": [judgment],
               "status": "incomplete",
               "rationale": "Physical numeric range and source-reviewed beam calibration are not yet constructed; exact selected cases retain judgment uncertainty.",
               "missing_inputs": ["source-reviewed physical sweep axes and finite grid"]}
              for index, judgment in enumerate(judgments, 1)]
    cases_stage = {"cell_id": "C230259", "actor": ACTOR, "status": "draft",
                   "cases": [baseline] + selected,
                   "comparisons": plan["comparisons"],
                   "sweep_specs": sweeps, "sweeps_expanded": True}
    return frozen_path, plan_path, relevance, template, bindings, cases_stage, judgments


def main():
    frozen_path, plan_path, relevance, template, bindings, cases, judgments = build()
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    refs = {name: _write(folder, name, value) for name, value in
            (("relevance_batch", relevance), ("relevance", relevance),
             ("template", template), ("bindings", bindings), ("cases", cases))}
    refs["judgment_observables"] = []
    channels = ("original_beam_pixels", "original_oncoming_distance", "original_actor_state")
    for index, judgment in enumerate(judgments, 1):
        channel = channels[index - 1]
        requirement = {"name": channel, "unit": "structured record",
                       "description": "Source-joined original observation for " + judgment["phrase"]}
        payload = {"template_id": TEMPLATE, "phrase": judgment["phrase"],
                   "note": judgment["note"], "status": "draft",
                   "observable_requirements": {"observables": [requirement],
                                               "context_inputs": [], "sweep_dimensions": [],
                                               "landmarks": [], "recording_needs": [requirement],
                                               "limitations": ["Independent original physical and legal review remains required."]}}
        refs["judgment_observables"].append(_write(folder, "judgment-" + str(index), payload))
    coverage_path = REPO / "inputs" / "coverage" / "branch-sources.json"
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "status": "draft", "physical_acceptance": "unverified",
             "sources": [{"path": str(path.relative_to(REPO)), "sha256": _hash(path)}
                         for path in (frozen_path, plan_path, coverage_path)],
             "stages": refs}
    (folder / "semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main()
