"""Draft source-bound semantic stages for the exact elevator case matrix.

The five-foot probes are geometric plans. They do not decide the statutory
measurement convention, object identity, necessity exception or legal verdict.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking import CASES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
LAW = "LVMC-11-52-130-A5"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
JUDGMENTS = (
    ("sidewalk elevator or chute", "Original fixture identity, frontage and side extent require review.", "fixture_geometry"),
    ("when necessary to avoid conflict with other traffic in compliance with law", "Original traffic and lawful necessity require review.", "traffic_conflict"),
    ("directions of a police officer", "Original officer direction and its applicability require review.", "police_direction"),
    ("directions of a traffic control device", "Original governing device and direction require review.", "traffic_device_direction"),
)


def _write(directory: Path, name: str, value: dict) -> dict:
    path = directory / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    exact_ids = [case["case_id"] for case in plan["cases"]]
    if exact_ids != [ASSIGNMENT + "__" + case.id for case in CASES]:
        raise ValueError("semantic proposal differs from exact case plan")
    quote = assignment["law"]["text"]
    directory = HERE / "proposals"
    directory.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": "C150153", "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                    "confidence": "low", "relevance_type": "sidewalk-elevator parking branch",
                                    "notes": "Original municipal site, fixture and activity still need review."}],
                 "borderline_excluded": []}
    stages = {"relevance_batch": _write(directory, "relevance_batch.json", relevance),
              "relevance": _write(directory, "relevance.json", relevance)}
    parameters = [
        {"name": "side_gap_m", "kind": "world_setup", "unit": "m",
         "range_or_domain": "commanded body-to-fixture side gap; actual body gap measured from original frames"},
        {"name": "side_region", "kind": "world_setup", "range_or_domain": "approach, front, west or east"},
        {"name": "activity", "kind": "controller", "range_or_domain": "stop, stand or park"},
        {"name": "exception_source", "kind": "world_setup",
         "range_or_domain": "none, lawful traffic conflict, police direction or traffic device direction"},
        {"name": "reviewed_site", "kind": "world_setup",
         "range_or_domain": "one original reviewed C150153 sidewalk elevator and municipal road"},
    ]
    template = {"status": "draft", "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": quote,
                "structure": {"activation": {"condition": "A person stops, stands or parks a vehicle beside a source-reviewed sidewalk elevator on the assigned municipal one-way road.",
                                             "numeric_conditions": []},
                              "obligation": {"type": "prohibition", "description": "No stopping, standing or parking in front of the fixture or in the five-foot side spaces absent a stated necessity exception. The 1.524 m probe is a geometric reference; boundary inclusion and measurement convention remain unresolved.",
                                             "numeric_conditions": [{"variable": "side_gap_m", "operator": "<=", "value": 1.524, "unit": "m"}]},
                              "exceptions": [{"source_clause": "except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device",
                                              "trigger": "source-reviewed traffic conflict or applicable direction",
                                              "effect": "the stated necessity exception may apply",
                                              "description": "Original source and lawful applicability remain unresolved."}],
                              "timing": {"description": "Original stop, stand or park interval and the complete 900-frame approach and release.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                        for phrase, note, _ in JUDGMENTS]},
                "parameter_refs": parameters}
    stages["template"] = _write(directory, "template.json", template)
    requirement_names = ("vehicle_body_footprint", "fixture_geometry", "activity_observation",
                         "traffic_conflict", "police_direction", "traffic_device_direction")
    channels = [{"name": name, "unit": "structured",
                 "method": "Original source-hashed observation joined to each Native frame",
                 "time_window": "all 900 original world ticks", "reference_frame": "reviewed C150153 Native map",
                 "sampling_rate_hz": 20, "uncertainty": "original realization and legal interpretation pending"}
                for name in requirement_names]
    description = {"channels": channels,
                   "context_inputs": [{"name": "reviewed_site", "unit": "structured",
                                       "method": "retained original municipal, sidewalk and elevator source inventory"}],
                   "limitations": ["Commanded gap and synthetic fixture do not establish original geometry or a legal result."]}
    judgment_refs = []
    for index, (phrase, note, observable) in enumerate(JUDGMENTS, 1):
        requirement = {"name": observable, "unit": "structured",
                       "description": "Original source and observation for " + phrase + "."}
        proposal = {"status": "draft", "template_id": TEMPLATE, "phrase": phrase, "note": note,
                    "observable_requirements": {"observables": [requirement],
                                                "context_inputs": [{"name": "reviewed_site", "unit": "structured",
                                                                    "description": "Original reviewed fixture and jurisdiction."}],
                                                "sweep_dimensions": [], "landmarks": [],
                                                "recording_needs": [requirement],
                                                "limitations": ["No synthetic source establishes legal applicability."]}}
        judgment_refs.append(_write(directory, f"judgment-{index}.json", proposal))
    stages["judgment_observables"] = judgment_refs
    binding = {"status": "draft", "cell_id": "C150153", "actor": ACTOR,
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [], "established_contexts": ["Frozen catalog cell; original site remains source-gated."],
               "fixed_parameters": [{"name": "assigned_cell", "value": "C150153",
                                     "rationale": "Frozen catalog identity, not reviewed physical placement."}],
               "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]}
    stages["bindings"] = _write(directory, "bindings.json", binding)
    baseline = {"side_gap_m": {"kind": "world_setup", "value": 0.0, "unit": "m"},
                "side_region": {"kind": "world_setup", "value": "approach"},
                "activity": {"kind": "controller", "value": "park"},
                "exception_source": {"kind": "world_setup", "value": "none"},
                "reviewed_site": {"kind": "world_setup", "value": "reviewed C150153 original site"}}
    cases = [{"case_id": ASSIGNMENT + "__semantic_baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared site setup; no separate recording.",
              "recording_description": description,
              "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
              "variable_assignments": baseline}]
    for case in CASES:
        values = json.loads(json.dumps(baseline))
        values["side_gap_m"]["value"] = case.gap_m
        values["side_region"]["value"] = case.region
        values["activity"]["value"] = case.activity
        values["exception_source"]["value"] = case.exception
        changed = [key for key in values if values[key]["value"] != baseline[key]["value"]]
        probe = {"primary_variable": "side_gap_m" if case.region != "front" else changed[0],
                 "comparison_or_standard": "statutory five-foot side space and controlled case plan",
                 "target_value_or_branch": case.id}
        if case.region != "front":
            probe.update({"threshold_ref": "obligation.numeric_conditions[0]",
                          "operator": "<=", "unit": "m", "test_value": case.gap_m})
        cases.append({"case_id": ASSIGNMENT + "__" + case.id, "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": "five_foot_side_gap" if case.region != "front" else "front_activity_exception",
                      "epsilon_used": 0.15 if case.region != "front" else None,
                      "deliberate_differences": changed, "probe": probe,
                      "rationale": "Original body footprint, fixture and necessity source decide the observed branch.",
                      "recording_description": description,
                      "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
                      "variable_assignments": values})
    sweeps = [{"sweep_id": f"pending-{index}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
               "missing_inputs": ["Original reviewed municipal site, fixture, activity and necessity sources"],
               "rationale": "Five feet is statutory; physical feasibility and judgment remain source-gated."}
              for index, (phrase, note, _) in enumerate(JUDGMENTS, 1)]
    stages["cases"] = _write(directory, "cases.json",
                              {"status": "draft", "cell_id": "C150153", "actor": ACTOR,
                               "cases": cases, "sweep_specs": sweeps, "sweeps_expanded": False})
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "stages": stages}
    (directory / "semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return {"stage_count": 9, "selected_cases": len(CASES), "status": "draft"}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
