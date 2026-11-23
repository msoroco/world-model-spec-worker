"""Write source-text semantic stage drafts pending exact case-pair completion."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from recording_description import build as recording_description

ROOT = Path(__file__).resolve().parent
LAW = "LVMC-11-60-090"
ACTOR = "taxi_driver"
CELL = "C150530"
QUOTE = ("Any cab, upon leaving any stand designated in accordance with the provisions "
         "of this Section, shall execute a right-hand turn, when a sign is posted "
         "giving notice of this requirement, at the first street intersection after "
         "it leaves such stand.")
TEMPLATE = LAW + "@" + ACTOR
PARAMETERS = [
    {"name": "stand_departure_x_m", "kind": "world_setup",
     "range_or_domain": "original route x coordinate in metres for source-reviewed stand departure"},
    {"name": "commanded_turn_path", "kind": "controller",
     "range_or_domain": "right turn or straight-through engineering route at first junction"},
]


def draft() -> dict:
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
                     "applies_to": [ACTOR], "relevance_type": "selected posted taxi-stand departure rule",
                     "confidence": "medium",
                     "notes": "The frozen assignment selects this law; original designation, licence, notice and jurisdiction records are still unbound."}],
                 "borderline_excluded": []}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": QUOTE,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "Cab leaves a stand designated under the referenced Section, with a posted sign giving notice of this requirement.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Execute a right-hand turn at the first street intersection after stand departure.",
                                   "type": "must", "numeric_conditions": []},
                    "exceptions": [],
                    "timing": {"description": "At the first street intersection after leaving the qualifying stand.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": []},
                "parameter_refs": PARAMETERS}
    bindings = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "established_contexts": ["candidate one-way junction and right-turn route; original source context pending"],
                "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [dict(p, used_by_laws=[LAW]) for p in PARAMETERS]}
    pair_id = "c150530-first-junction-two-axis"
    def assignments(departure_x: float, path: str) -> dict:
        return {
            "stand_departure_x_m": {"kind": "world_setup", "value": departure_x,
                                    "unit": "m", "note": "Candidate departure x; source designation remains unverified"},
            "commanded_turn_path": {"kind": "controller", "value": path,
                                    "note": "Engineering route request, not measured behavior"},
        }

    def case(suffix: str, target_type: str, departure_x: float, path: str,
             differences: list[str], rationale: str) -> dict:
        item = {"case_id": "testing__C150530__LVMC-11-60-090__taxi_driver__" + suffix,
                "target_law_id": None if target_type == "baseline" else LAW,
                "target_type": target_type, "rationale": rationale,
                "variable_assignments": assignments(departure_x, path),
                "recording_description": recording_description(),
                "unresolved_judgment_calls": []}
        if target_type != "baseline":
            item.update({"paired_probe_id": pair_id,
                         "deliberate_differences": differences,
                         "probe": {"primary_variable": ("stand_departure_x_m" if suffix == "far_stand"
                                                       else "commanded_turn_path"),
                                   "comparison_or_standard": "Original first-junction route, held source guards and stand position where compared; no distance legal threshold",
                                   "target_value_or_branch": path if suffix != "far_stand" else departure_x}})
        return item

    cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
             "cases": [
                 case("baseline", "baseline", -48.0, "right", [],
                      "Neutral source-guarded near-stand candidate definition; no simulation or legal label."),
                 case("near_stand", "compliant_attempt", -48.0, "right",
                      ["stand_departure_x_m", "commanded_turn_path"],
                      "Right-turn attempt at first junction from near stand; actual behavior and applicability pending."),
                 case("far_stand", "compliant_attempt", -68.0, "right",
                      ["stand_departure_x_m"],
                      "Same right-turn attempt with stand/departure shifted 20 m upstream; no legal distance threshold."),
                 case("near_stand_straight", "violating_attempt", -48.0, "straight",
                      ["commanded_turn_path"],
                      "Straight-through attempt at first junction with near stand and notice held fixed; no legal verdict."),
             ], "sweep_specs": []}
    return {"relevance_batch": relevance, "relevance": relevance,
            "template": template, "bindings": bindings, "cases": cases}


def main() -> None:
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    for stage, value in draft().items():
        (folder / (stage + ".json")).write_text(json.dumps(value, indent=2) + "\n")
    references = {}
    for stage in ("relevance_batch", "relevance", "template", "bindings", "cases"):
        path = folder / (stage + ".json")
        references[stage] = {"path": "proposals/" + path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    references["judgment_observables"] = []
    index = {"format": "worker-semantic-delivery",
             "assignment_id": "testing__C150530__LVMC-11-60-090__taxi_driver",
             "stages": references}
    (folder / "semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main()
