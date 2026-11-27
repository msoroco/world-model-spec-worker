"""Author the assignment's draft semantic chain from its exact source text."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / "proposals"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(name: str, value: dict) -> dict:
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": "proposals/" + name, "sha256": _sha(path)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    base_suffixes = {"slow_center_wide", "slow_right_wide", "slow_center_narrow",
                     "slow_center_no_follower", "slow_center_obstruction_near"}
    plan["cases"] = [row for row in plan["cases"]
                     if row["case_id"].rsplit("__", 1)[-1] in base_suffixes]
    plan["comparisons"] = [row for row in plan["comparisons"]
                           if not row["comparison_id"].endswith("_engineering_sweep")]
    construction = json.loads((ROOT / "construction.json").read_text(encoding="utf-8"))
    aid, law, cell, actor = (plan[key] for key in ("assignment_id", "law_id", "cell_id", "actor"))
    quote = plan["law_text"]
    description = construction["recording_description"]
    relevance = _write("relevance.json", {
        "cell_id": cell, "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
            "relevance_type": "specific_match", "confidence": "low",
            "notes": "One lane each direction is compatible with the cell; impediment, paved width and NRS 484B.630 applicability remain source questions."}],
        "borderline_excluded": []})
    variables = {"ego_path": "controller", "pavement_variant": "world_setup",
                 "immediate_follower_requested": "world_setup", "obstruction_variant": "world_setup",
                 "ego_speed_mps": "controller", "paved_right_edge_m": "world_setup",
                 "ego_path_offset_m": "controller"}
    refs = [{"name": key, "kind": kind,
             "range_or_domain": "exact source-reviewed site variant; requested engineering value, not legal standard"}
            for key, kind in variables.items()]
    judgments = [
        ("so slow as to impede the forward movement of traffic proceeding immediately behind",
         "Distinct original follower and subject histories required; no legal speed or gap cutoff.",
         "ego_speed_mps", "m/s"),
        ("the width of the paved portion permits",
         "Actual paved edge, body footprint and obstruction require review; no clearance cutoff.",
         "paved_right_edge_m", "m"),
        ("extreme right side of the highway",
         "Original highway edge, paved edge and subject footprint require review; no lateral cutoff.",
         "ego_path_offset_m", "m"),
    ]
    template = _write("template.json", {
        "template_id": law + "@" + actor, "law_id": law, "actor": actor,
        "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "Motor-vehicle driver travels so slowly as to impede traffic immediately behind on a highway with one lane in each direction, if paved width permits.",
                           "numeric_conditions": []},
            "obligation": {"description": "Drive to the extreme right side and, if applicable, comply with NRS 484B.630.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "During the qualifying slow-drive episode; NRS 484B.630 applicability and timing remain unresolved.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _, _ in judgments]},
        "parameter_refs": refs})
    judgment_refs = []
    for index, (phrase, note, observable, unit) in enumerate(judgments):
        judgment_refs.append(_write(f"judgment-{index}.json", {
            "template_id": law + "@" + actor, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": {
                "context_inputs": [{"name": "original_highway_and_cross_reference", "unit": "source record",
                    "description": "SHA-bound original two-way site and conditional NRS 484B.630 context"}],
                "landmarks": [],
                "limitations": ["No original recording exists in the frozen evidence inventory; no fixture proves a legal judgment."],
                "observables": [{"name": observable, "unit": unit,
                    "description": "Original 20 Hz participant, body, paved-edge and obstruction history"}],
                "recording_needs": [{"name": observable, "unit": unit,
                    "description": "Retain the original source and synchronized four-view camera frames"}],
                "sweep_dimensions": [{"name": "ego_speed_mps" if index == 0 else "paved_right_edge_m" if index == 1 else "ego_path_offset_m",
                    "unit": "m/s" if index == 0 else "m",
                    "description": "Engineering coverage variable only; not a legal standard"}]}}))
    binding = _write("bindings.json", {
        "cell_id": cell, "actor": actor, "status": "draft",
        "established_contexts": ["Two-way travel with a physical roadside obstruction and a separate traffic participant; precise legal applicability remains unresolved."],
        "law_refs": [{"template_id": law + "@" + actor, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "maneuver", "kind": "world_setup", "value": "travel",
                              "source": "frozen C323986 cell"}],
        "variable_parameters": [dict(item, used_by_laws=[law]) for item in refs]})
    cases = [{"case_id": aid + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Unexecuted comparison reference.",
        "variable_assignments": {name: {"kind": kind, "value": "unselected"}
                                 for name, kind in variables.items()},
        "unresolved_judgment_calls": [], "recording_description": description}]
    for row in plan["cases"]:
        row["recording_description"] = description
        suffix = row["case_id"].rsplit("__", 1)[-1]
        differences = {"slow_center_wide": ["ego_path", "ego_path_offset_m"],
                       "slow_right_wide": ["ego_path", "ego_path_offset_m"],
                       "slow_center_narrow": ["pavement_variant", "paved_right_edge_m"],
                       "slow_center_no_follower": ["immediate_follower_requested"],
                       "slow_center_obstruction_near": ["obstruction_variant"]}[suffix]
        primary = differences[0]
        values = {"ego_path": row["ego_path"], "pavement_variant": row["pavement_variant"],
                  "immediate_follower_requested": row["immediate_follower_requested"],
                  "obstruction_variant": row["obstruction_variant"],
                  "ego_speed_mps": 5.0,
                  "paved_right_edge_m": 3.5 if row["pavement_variant"] == "narrow" else 4.7,
                  "ego_path_offset_m": 1.1 if row["ego_path"] == "right" else 0.0}
        cases.append({"case_id": row["case_id"], "target_law_id": law,
            "target_type": "boundary_probe",
            "rationale": "Controlled original two-way, follower, paved-width, right-position and obstruction comparison; legal judgments unresolved.",
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                                     for name, kind in variables.items()},
            "unresolved_judgment_calls": [phrase for phrase, _, _, _ in judgments],
            "paired_probe_id": next((c["comparison_id"] for c in plan["comparisons"]
                                    if row["case_id"] in c["case_ids"]), "right_side_position"),
            "deliberate_differences": differences,
            "probe": {"primary_variable": primary, "comparison_or_standard": "original physical source review",
                      "target_value_or_branch": row["case_id"].rsplit("__", 1)[-1]},
            "recording_description": description})
    def assignments():
        return {"ego_path": {"kind": "controller", "value": "center"},
                "pavement_variant": {"kind": "world_setup", "value": "wide"},
                "immediate_follower_requested": {"kind": "world_setup", "value": True},
                "obstruction_variant": {"kind": "world_setup", "value": "far"},
                "ego_speed_mps": {"kind": "controller", "value": 5.0},
                "paved_right_edge_m": {"kind": "world_setup", "value": 4.7},
                "ego_path_offset_m": {"kind": "controller", "value": 0.0}}
    sweep_specs = []
    for index, (name, variable, observable, unit, low, high, spacing, method) in enumerate((
        ("impediment", "ego_speed_mps", "ego_speed_mps", "m/s", 4.0, 6.0, 1.0,
         "mean original 20 Hz subject speed readback"),
        ("paved_width", "paved_right_edge_m", "paved_right_edge_m", "m", 3.5, 4.7, 0.6,
         "first original paved right-edge readback"),
        ("right_position", "ego_path_offset_m", "ego_path_offset_m", "m", 0.0, 1.1, 0.55,
         "mean original subject body center relative travel lane"),
    )):
        assignment = assignments()
        if name == "right_position":
            assignment["ego_path"]["value"] = "right"
        sweep_specs.append({"sweep_id": aid + "__" + name,
            "target_law_id": law, "judgment_refs": [{"phrase": judgments[index][0],
                                                      "note": judgments[index][1]}],
            "rationale": "Three source-gated physical engineering samples; no legal judgment or physical outcome is asserted.",
            "status": "complete", "mode": "one_dimensional", "landmarks": [],
            "variable_assignments": assignment, "recording_description": description,
            "axes": [{"variable": variable, "observable": observable,
                "unit": unit, "min": low, "max": high, "spacing": spacing,
                "range_rationale": "Ordinary vehicle and roadside geometry engineering requests; original map/controller feasibility must be source reviewed.",
                "spacing_rationale": "Three distinct requests larger than the 20 Hz sampling resolution; actual values require original readback.",
                "feasibility_evidence": "reviewed_scene.py requires exact source-reviewed original case geometry and native_adapter.py records actual state; synthetic CPU tests exercise every request.",
                "measurement": {"method": method, "time_window": "full original 45-second episode",
                                "statistic": "mean" if name != "paved_width" else "first"}}]})
    result = {"cell_id": cell, "actor": actor, "status": "draft",
              "cases": cases, "sweep_specs": sweep_specs}
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before importing runtime")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(result, [json.loads((OUT / "template.json").read_text())],
                  json.loads((OUT / "bindings.json").read_text()))
    case_ref = _write("cases.json", result)
    selected = [item for item in result["cases"] if item["target_type"] != "baseline"]
    for item in selected[5:]:
        suffix = item["case_id"].rsplit("__", 1)[-1]
        values = {key: value["value"] for key, value in item["variable_assignments"].items()}
        plan["cases"].append({"case_id": item["case_id"], "target_law_id": law,
            "kind": "delivery", "new_capture_selected": True,
            "gap_ids": [gap["id"] for gap in plan["evidence_review"]["gaps"]],
            "branch": plan["selected_branch"], "ego_path": values["ego_path"],
            "pavement_variant": values["pavement_variant"],
            "immediate_follower_requested": values["immediate_follower_requested"],
            "obstruction_variant": values["obstruction_variant"],
            "target": values, "recording_description": description,
            "physical_risk": {"status": "physical", "reason":
                "Original right-side prop clearance and participant motion require physical review."},
            "legal_judgment": "unresolved"})
    for name in ("impediment", "paved_width", "right_position"):
        members = [item["case_id"] for item in selected if item.get("sweep_id", "").endswith("__" + name)]
        plan["comparisons"].append({"comparison_id": name + "_engineering_sweep",
            "case_ids": members,
            "fixed_conditions": ["Same source-reviewed two-way road, physical obstruction, follower, capture and non-axis controller requests."],
            "deliberate_differences": ["Requested engineering " + name + " value only"]})
    for disposition in plan["requirement_dispositions"]:
        disposition["case_ids"] = [item["case_id"] for item in selected]
    (ROOT / "case-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    source = REPO / "inputs" / aid / "assignment.json"
    _write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": aid,
        "source": {"path": source.relative_to(REPO).as_posix(), "sha256": _sha(source)},
        "stages": {"relevance_batch": relevance, "relevance": relevance,
                   "template": template, "judgment_observables": judgment_refs,
                   "bindings": binding, "cases": case_ref},
        "status": "draft_original_source_review_pending"})


if __name__ == "__main__":
    main()
