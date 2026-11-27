"""Author exact NRS 484B.297(2) proposals for local staged review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "proposals"
LAW = "NRS-484B-297-2"
ACTOR = "pedestrian"
TEMPLATE = LAW + "@" + ACTOR


def write(name: str, value: dict) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path.relative_to(HERE)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": plan["cell_id"], "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low", "relevance_type": "specific_match",
        "notes": "No-sidewalk longitudinal walking and public-highway status require reviewed original source."}], borderline_excluded=[])
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    variables = (("pedestrian_route_side", "left or right highway side", "controller"),
                 ("approaching_vehicle_direction", "eastbound or westbound", "world_setup"),
                 ("pedestrian_heading", "facing or with approaching traffic", "controller"))
    template_ref = write("template.json", {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain} for name, domain, kind in variables],
        "structure": {"law_id": LAW,
            "activation": {"condition": "A pedestrian walks along a public highway where a qualifying sidewalk is not provided; subsection 6 sidewalk-obstruction detour is inapplicable.", "numeric_conditions": []},
            "obligation": {"type": "walk_left_facing_approach", "description": quote, "numeric_conditions": []},
            "exceptions": [{"source_clause": "Except as otherwise provided in subsection 6 [NRS-484B-297-6]", "description": "A sidewalk traveler may detour around an obstruction under subsection 6; applicability requires separate source review and is not presumed in this no-sidewalk cell."}],
            "timing": {"description": "Observe original pedestrian position and heading, highway boundaries and approaching traffic route throughout longitudinal walking.", "numeric_conditions": []},
            "judgment_calls_needed": []}})
    bindings_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C233658 road_without_sidewalk, straight pedestrian walking and other_vehicle; physical public-highway and sidewalk status pending original source review."],
        fixed_parameters=[{"name": "assigned_cell", "value": "C233658", "rationale": "Frozen catalog identity, not original public-highway evidence."}],
        variable_parameters=[{"name": name, "kind": kind, "range_or_domain": domain, "used_by_laws": [LAW]} for name, domain, kind in variables]))
    first = json.loads((HERE / "cases/east_approach_left_side/construction.json").read_text(encoding="utf-8"))["recording_description"]
    cases = [{"case_id": HERE.name + "__baseline", "target_law_id": None, "target_type": "baseline",
              "rationale": "Shared source-gated walking site reference; not selected for recording.",
              "variable_assignments": {"pedestrian_route_side": {"kind": "controller", "value": "left"},
                                       "approaching_vehicle_direction": {"kind": "world_setup", "value": "east"},
                                       "pedestrian_heading": {"kind": "controller", "value": "facing"}},
              "recording_description": first, "unresolved_judgment_calls": []}]
    for case in plan["cases"]:
        short = case["case_id"].split("__")[-1]
        description = json.loads((HERE / "cases" / short / "construction.json").read_text(encoding="utf-8"))["recording_description"]
        values = {"pedestrian_route_side": case["pedestrian_highway_side"],
                  "approaching_vehicle_direction": case["approach_direction"],
                  "pedestrian_heading": case["pedestrian_heading"]}
        heading_probe = values["pedestrian_heading"] == "with_traffic"
        primary = "pedestrian_heading" if heading_probe else "pedestrian_route_side"
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "compliant_attempt" if values["pedestrian_route_side"] == "left" and not heading_probe else "violating_attempt",
            "rationale": "Requested route side and approach are physical targets; actual original trajectories and site qualifications decide the delivered scenario outcome.",
            "variable_assignments": {name: {"kind": kind, "value": values[name]} for name, _, kind in variables},
            "paired_probe_id": values["approaching_vehicle_direction"] + "_approach_side_and_facing",
            "deliberate_differences": [primary],
            "probe": {"primary_variable": primary,
                      "comparison_or_standard": "same reviewed no-sidewalk public highway, approach route, pedestrian heading and four-camera policy",
                      "target_value_or_branch": values[primary]},
            "unresolved_judgment_calls": [], "recording_description": description})
    cases_ref = write("cases.json", dict(common, cases=cases, sweep_specs=[]))
    write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
        "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": bindings_ref, "cases": cases_ref}})


if __name__ == "__main__":
    build()
