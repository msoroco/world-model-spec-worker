"""Author source-grounded canonical semantic proposals for eight exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = "NRS-486-351-1"
CELL = "C145696"
ACTOR = "motorcycle_or_moped_operator"
TEXT = ("A person, except a police officer in the performance of his or her duty, "
        "shall not drive a motorcycle or moped between moving or stationary vehicles "
        "occupying adjacent traffic lanes.")
CHANNELS = ("adjacent_lane_occupancy", "between_vehicle_passage", "vehicle_motion",
            "ego_vehicle_class", "police_duty_exception", "four_camera_visibility")
RECORDING = {
    "channels": [{"name": name, "unit": "original-frame structured record", "sampling_rate_hz": 20,
                  "method": "source-bound original Native participant and map readback",
                  "time_window": "entire one-way 45s passage episode",
                  "reference_frame": "original CARLA frame, elapsed time and surveyed road axis",
                  "uncertainty": "20 Hz sampling; legal between/adjacent interpretation and pixels need independent review"}
                 for name in CHANNELS],
    "context_inputs": [{"name": name, "unit": "source packet",
                        "method": "independently reviewed original source bytes"}
                       for name in ("jurisdiction", "lane_geometry_source", "operator_identity_source",
                                    "police_status_source", "performance_of_duty_source",
                                    "chapter_vehicle_classification_source")],
    "limitations": ["Between-vehicle and adjacent-lane interpretation has no invented geometric cutoff.",
                    "Original police duty and chapter vehicle class require independent source review.",
                    "Actual pixels and passage require local Native recording and audit."]}
PARAMETERS = (
    ("left_motion", "world_setup", "stationary or moving"),
    ("right_motion", "world_setup", "stationary or moving"),
    ("maneuver", "controller", "between or within_left"),
    ("vehicle_class", "world_setup", "motorcycle or moped"),
    ("operator_status", "world_setup", "civilian or police"),
    ("performance_of_duty", "world_setup", "not_applicable, on_duty or off_duty"),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    p = ROOT / "proposals"
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT, "applies_to": [ACTOR],
                                    "relevance_type": "direct motorcycle/moped adjacent-lane driving prohibition",
                                    "confidence": "high",
                                    "notes": "Chapter vehicle class, adjacent occupancy, passage and duty remain source-gated."}],
                 "borderline_excluded": []}
    write(p / "relevance.json", relevance)
    write(p / "relevance_batch.json", relevance)
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "quote": TEXT,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A person drives a motorcycle or moped between moving or stationary vehicles in adjacent traffic lanes.",
                                             "numeric_conditions": []},
                              "obligation": {"description": TEXT, "type": "must_not",
                                             "numeric_conditions": []},
                              "exceptions": [{"trigger": "A police officer acts in the performance of duty.",
                                              "effect": "The stated prohibition does not apply to that officer.",
                                              "replacement_obligation": "None specified by NRS 486.351(1).",
                                              "source_clause": "except a police officer in the performance of his or her duty"}],
                              "timing": {"description": "During the original between-vehicle driving episode.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": []},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in PARAMETERS]}
    write(p / "template.json", template)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": ["one-way multilane road", "two adjacent occupied traffic lanes",
                                        "motorcycle or moped passage route"],
               "law_refs": [{"template_id": LAW + "@" + ACTOR, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain, "used_by_laws": [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    write(p / "bindings.json", binding)
    cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": [], "sweep_specs": []}
    baseline_parameters = plan["cases"][0]["scenario_parameters"]
    cases["cases"].append({"case_id": AID + "__baseline", "target_law_id": None,
                           "target_type": "baseline",
                           "rationale": "Shared stationary adjacent-lane reference; no separate recording.",
                           "variable_assignments": {
                               name: {"kind": kind, "value": baseline_parameters[name]}
                               for name, kind, _ in PARAMETERS},
                           "unresolved_judgment_calls": [],
                           "recording_description": RECORDING})
    for item in plan["cases"]:
        params = item["scenario_parameters"]
        suffix = item["case_id"].split("__")[-1]
        variables = {name: {"kind": kind, "value": params[name]} for name, kind, _ in PARAMETERS}
        cases["cases"].append({"case_id": item["case_id"], "target_law_id": LAW,
                               "target_type": "compliant_attempt" if suffix in
                               ("within_left", "police_on_duty") else "violating_attempt",
                               "rationale": "Source-bound adjacent-lane, movement, route, vehicle-class and duty contrast; no verdict inferred.",
                               "variable_assignments": variables,
                               "unresolved_judgment_calls": ["between-vehicle driving",
                                                             "adjacent-lane occupancy",
                                                             "chapter vehicle class",
                                                             "police performance of duty"],
                               "recording_description": RECORDING,
                               "paired_probe_id": "adjacent_lane_passage",
                               "deliberate_differences": list(variables),
                               "probe": {"primary_variable": "maneuver",
                                         "comparison_or_standard": "original source-bound controlled contrast",
                                         "target_value_or_branch": params["maneuver"]}})
    write(p / "cases.json", cases)
    refs = {stage: {"path": "proposals/" + stage + ".json",
                    "sha256": hashlib.sha256((p / (stage + ".json")).read_bytes()).hexdigest()}
            for stage in ("relevance_batch", "relevance", "template", "bindings", "cases")}
    refs["judgment_observables"] = []
    write(p / "semantic-index.json", {"format": "worker-semantic-delivery",
                                      "assignment_id": AID, "stages": refs})


if __name__ == "__main__":
    main()
