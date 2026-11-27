"""Author the assignment's draft semantic chain from its exact source text."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
                 "ego_speed_mps": "controller"}
    refs = [{"name": key, "kind": kind,
             "range_or_domain": "exact source-reviewed site variant; requested engineering value, not legal standard"}
            for key, kind in variables.items()]
    judgments = [
        ("so slow as to impede the forward movement of traffic proceeding immediately behind",
         "Distinct original follower and subject histories required; no legal speed or gap cutoff.",
         "following_progress", "m and m/s"),
        ("the width of the paved portion permits",
         "Actual paved edge, body footprint and obstruction require review; no clearance cutoff.",
         "right_side_clearance", "m"),
        ("extreme right side of the highway",
         "Original highway edge, paved edge and subject footprint require review; no lateral cutoff.",
         "body_right_position", "m"),
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
                "sweep_dimensions": [{"name": "ego_speed_mps" if index == 0 else "pavement_variant" if index == 1 else "ego_path",
                    "unit": "m/s" if index == 0 else "physical source variant",
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
        values = {"ego_path": row["ego_path"], "pavement_variant": row["pavement_variant"],
                  "immediate_follower_requested": row["immediate_follower_requested"],
                  "obstruction_variant": row["obstruction_variant"],
                  "ego_speed_mps": 5.0}
        cases.append({"case_id": row["case_id"], "target_law_id": law,
            "target_type": "boundary_probe",
            "rationale": "Controlled original two-way, follower, paved-width, right-position and obstruction comparison; legal judgments unresolved.",
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                                     for name, kind in variables.items()},
            "unresolved_judgment_calls": [phrase for phrase, _, _, _ in judgments],
            "paired_probe_id": next((c["comparison_id"] for c in plan["comparisons"]
                                    if row["case_id"] in c["case_ids"]), "right_side_position"),
            "deliberate_differences": ["exact declared comparison variable"],
            "probe": {"primary_variable": "ego_path", "comparison_or_standard": "original physical source review",
                      "target_value_or_branch": row["case_id"].rsplit("__", 1)[-1]},
            "recording_description": description})
    case_ref = _write("cases.json", {"cell_id": cell, "actor": actor, "status": "draft",
                                     "cases": cases, "sweep_specs": []})
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
