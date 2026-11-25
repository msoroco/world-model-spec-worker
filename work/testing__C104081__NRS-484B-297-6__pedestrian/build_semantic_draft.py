"""Write exact draft semantic proposals for the five sidewalk bypass cases.

Judgment sweeps stay incomplete until a reviewed original hill-crest source can
support feasible ranges. These proposals make no compliance classification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_offline_draft import RECORDING_DESCRIPTION

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
LAW = "NRS-484B-297-6"
TEMPLATE = LAW + "@pedestrian"
PHRASES = (
    "with due care",
    "as far to the side of the highway near the sidewalk as possible",
    "if the area between the lane and the sidewalk is impassable",
    "as soon as practicable",
)
PARAMETERS = (
    ("pedestrian_direction", "world_setup", "same or opposite surveyed sidewalk travel direction"),
    ("intervening_area_blocked", "world_setup", "source-surveyed traversable or impassable"),
    ("sidewalk_obstruction_end_m", "world_setup", "source-surveyed local route distance in metres"),
    ("sidewalk_obstruction_kind", "world_setup", "impassable or missing sidewalk section"),
)


def _write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((ROOT.parents[1] / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    law = assignment["law"]["text"]
    plan = json.loads((ROOT / "case-plan.json").read_text())
    relevance = {
        "cell_id": "C104081", "actor": "pedestrian", "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": law, "applies_to": ["pedestrian"],
                           "relevance_type": "direct sidewalk obstruction bypass",
                           "confidence": "high",
                           "notes": "Exact frozen cell selects a pedestrian on the hill-crest sidewalk."}],
        "borderline_excluded": [],
    }
    parameter_refs = [{"name": name, "kind": kind, "range_or_domain": domain}
                      for name, kind, domain in PARAMETERS]
    template = {
        "template_id": TEMPLATE, "law_id": LAW, "actor": "pedestrian", "quote": law,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "A pedestrian on a sidewalk encounters a mobility obstruction, including a missing or impassable short section.", "numeric_conditions": []},
            "obligation": {"description": "A sidewalk bypass may use the immediately adjacent highway with due care, while retaining the stated side, direction, bicycle-lane and return conditions.",
                           "type": "may_with_conditions", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Observe obstacle encounter, bypass, traffic, and first practicable sidewalk return on one original clock.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase,
                                       "note": "Requires source-reviewed physical context; no synthetic cutoff or legal verdict."}
                                      for phrase in PHRASES],
        },
        "parameter_refs": parameter_refs,
    }
    judgments = []
    for index, phrase in enumerate(PHRASES, 1):
        observable = {
            "template_id": TEMPLATE, "phrase": phrase,
            "note": "Requires source-reviewed physical context; no synthetic cutoff or legal verdict.",
            "status": "draft",
            "observable_requirements": {
                "observables": [{"name": "pedestrian_body_center_xy_m", "unit": "structured",
                                 "description": "Original pedestrian body center across the bypass."}],
                "context_inputs": [{"name": "source_provenance", "unit": "metadata",
                                    "description": "Original surveyed map, obstacle, traffic and camera source identities."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "pedestrian_body_center_xy_m", "unit": "structured",
                                     "description": "Timestamped original pedestrian body positions."}],
                "limitations": ["Reviewed local map and participant observations are absent from the frozen export."],
            },
        }
        judgments.append(_write(f"judgment-{index}.json", observable))
    bindings = {
        "cell_id": "C104081", "actor": "pedestrian", "status": "draft",
        "established_contexts": ["hill-crest pedestrian sidewalk bypass in frozen cell"],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(parameter, used_by_laws=[LAW]) for parameter in parameter_refs],
    }
    def assignments(values):
        return {name: {"kind": kind, "value": values[name]}
                for name, kind, _ in PARAMETERS}
    baseline_values = {"pedestrian_direction": 1, "intervening_area_blocked": False,
                       "sidewalk_obstruction_end_m": 34,
                       "sidewalk_obstruction_kind": "impassable_section"}
    baseline = {
        "case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared reference for authored bypass comparisons.",
        "variable_assignments": assignments(baseline_values),
        "recording_description": RECORDING_DESCRIPTION,
        "unresolved_judgment_calls": list(PHRASES),
    }
    cases = [baseline]
    for entry in plan["cases"]:
        params = entry["construction_parameters"]
        values = {"pedestrian_direction": params["direction"],
                  "intervening_area_blocked": params["area_blocked"],
                  "sidewalk_obstruction_end_m": params["sidewalk_end_m"],
                  "sidewalk_obstruction_kind": params["obstruction_kind"]}
        differing = [name for name in values if values[name] != baseline_values[name]]
        primary = differing[0] if differing else "intervening_area_blocked"
        cases.append({
            "case_id": entry["case_id"], "target_law_id": LAW,
            "target_type": "judgment_sweep", "rationale": entry["review_description"],
            "variable_assignments": assignments(values),
            "paired_probe_id": entry["case_id"].rsplit("__", 1)[-1],
            "deliberate_differences": differing or [primary],
            "probe": {"primary_variable": primary,
                      "comparison_or_standard": "source-reviewed sidewalk bypass context",
                      "target_value_or_branch": values[primary]},
            "recording_description": RECORDING_DESCRIPTION,
            "unresolved_judgment_calls": list(PHRASES),
        })
    sweep_specs = [{"sweep_id": f"sidewalk-judgment-{i}", "target_law_id": LAW,
                    "judgment_refs": [{"phrase": phrase,
                                       "note": "Requires source-reviewed physical context; no synthetic cutoff or legal verdict."}],
                    "rationale": "No legal or physical cutoff can be inferred from diagnostic geometry.",
                    "status": "incomplete",
                    "missing_inputs": ["original hill-crest site survey", "reviewed original participant observations"]}
                   for i, phrase in enumerate(PHRASES, 1)]
    case_proposal = {"cell_id": "C104081", "actor": "pedestrian", "status": "draft",
                     "cases": cases, "sweep_specs": sweep_specs, "diagnostic_only": True}
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": {
                 "relevance_batch": _write("relevance_batch.json", relevance),
                 "relevance": _write("relevance.json", relevance),
                 "template": _write("template.json", template),
                 "judgment_observables": judgments,
                 "bindings": _write("bindings.json", bindings),
                 "cases": _write("cases.json", case_proposal),
             }}
    _write("semantic-index.json", index)
    print("draft semantic proposals built for", len(cases) - 1, "exact cases")


if __name__ == "__main__":
    build()
