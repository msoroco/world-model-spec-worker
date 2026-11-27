"""Author draft canonical semantic stages for the exact roadway-stop law."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from stop_model import ASSIGNMENT, CASES, LAW


ROOT = Path(__file__).resolve().parent
ACTOR = "motor_vehicle_driver"
CELL = "C150640"
TEXT = ("A person shall not bring a vehicle to a complete stop upon a roadway so as to "
        "impede or block the normal and reasonable movement of traffic unless the stop "
        "is necessary for safe operation or in compliance with law.")
PHRASES = [
    {"phrase": "normal and reasonable movement of traffic",
     "note": "Original follower motion, route and available passage matter; delay is not a legal cutoff."},
    {"phrase": "necessary for safe operation",
     "note": "Original conflict and alternative maneuvers require independent review; proximity is not necessity."},
]
CHANNELS = ("scene_source", "one_way_route", "ego_driver_and_vehicle", "ego_motion",
            "roadway_footprint", "follower_motion", "passing_space", "stop_purpose",
            "conflict_context", "official_direction_context", "camera_frame_map")
CONTEXTS = ("jurisdiction", "roadway_boundary", "shoulder_boundary",
            "one_way_direction", "follower_driver")
RECORDING = {
    "channels": [{"name": name, "unit": "structured record", "sampling_rate_hz": 20,
                  "method": "Original Native readback joined to saved-only stop measurement",
                  "time_window": "one-way approach, stop or slow roll, and follower response",
                  "reference_frame": "original CARLA frame/time and map coordinates",
                  "uncertainty": "20 Hz sampling; observed traffic effect and causes require independent review"}
                 for name in CHANNELS],
    "context_inputs": [{"name": name, "unit": "source packet",
                        "method": "Original reviewed map and jurisdiction source"}
                       for name in CONTEXTS],
    "limitations": ["Normal and reasonable movement and safety necessity remain open judgments.",
                    "Official direction must be checked against the applicable original law."]}
PARAMETERS = (
    ("stop_surface", "world_setup", "roadway or shoulder"),
    ("stop_reason", "world_setup", "destination, safety conflict, or official direction"),
    ("follower_action", "controller", "follow and halt or pass"),
    ("complete_stop_requested", "controller", "true or false"),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    proposal_dir = ROOT / "proposals"
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT,
                                    "applies_to": [ACTOR], "relevance_type": "specific_match",
                                    "confidence": "high",
                                    "notes": "One-way destination stop could impede following traffic; exceptions are conditional."}],
                 "borderline_excluded": []}
    write(proposal_dir / "relevance.json", relevance)
    write(proposal_dir / "relevance_batch.json", relevance)
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "quote": TEXT,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "A person brings a vehicle to a complete stop upon a roadway and affects traffic movement.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Do not stop so as to impede or block normal and reasonable traffic movement without an exception.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [
                                  {"trigger": "stop necessary for safe operation", "effect": "exception",
                                   "replacement_obligation": "none supplied by this paragraph",
                                   "source_clause": "unless the stop is necessary for safe operation"},
                                  {"trigger": "stop in compliance with law", "effect": "exception",
                                   "replacement_obligation": "none supplied by this paragraph",
                                   "source_clause": "or in compliance with law"}],
                              "timing": {"description": "At the complete stop and ensuing traffic interaction.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": PHRASES},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in PARAMETERS]}
    write(proposal_dir / "template.json", template)
    judgments = []
    for index, phrase in enumerate(PHRASES):
        if index == 0:
            observed = ["follower_motion", "passing_space", "ego_motion"]
            dimensions = ["follower_motion"]
        else:
            observed = ["conflict_context", "ego_motion", "stop_purpose"]
            dimensions = ["conflict_context"]
        requirements = {
            "observables": [{"name": name, "unit": "structured record",
                             "description": "Original synchronized source-bound event history"} for name in observed],
            "context_inputs": [{"name": "jurisdiction", "unit": "source packet",
                                "description": "Reviewed original public-highway and roadway source"}],
            "sweep_dimensions": [{"name": name, "unit": "structured record",
                                  "description": "Potential measured physical variation, without judgment cutoff"}
                                 for name in dimensions],
            "landmarks": [],
            "recording_needs": [{"name": name, "unit": "structured record",
                                 "description": "Original raw Native history for later independent review"}
                                for name in observed],
            "limitations": ["Raw motion and context do not determine a statutory meaning or legal conclusion."]}
        item = {"template_id": template["template_id"], "phrase": phrase["phrase"],
                "note": phrase["note"], "status": "draft",
                "observable_requirements": requirements}
        filename = f"judgment-{index}.json"
        write(proposal_dir / filename, item)
        judgments.append(filename)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": ["one-way road", "stop_stand", "other vehicle"],
               "law_refs": [{"template_id": template["template_id"], "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                        "used_by_laws": [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    write(proposal_dir / "bindings.json", binding)
    cases = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": [],
             "sweep_specs": [], "sweeps_expanded": True}
    neutral = CASES[0]
    cases["cases"].append({"case_id": ASSIGNMENT + "__baseline",
                           "target_law_id": None, "target_type": "baseline",
                           "rationale": "Neutral source-reviewed reference definition, not a recording.",
                           "variable_assignments": {name: {"kind": kind, "value": getattr(neutral, name)}
                                                    for name, kind, _ in PARAMETERS},
                           "unresolved_judgment_calls": [],
                           "recording_description": RECORDING})
    for case in CASES:
        assignments = {name: {"kind": kind, "value": getattr(case, name)}
                       for name, kind, _ in PARAMETERS}
        changed = [name for name, _, _ in PARAMETERS
                   if getattr(case, name) != getattr(neutral, name)]
        cases["cases"].append({"case_id": ASSIGNMENT + "__" + case.name,
                               "target_law_id": LAW, "target_type": "boundary_probe",
                               "rationale": "Source-bound stop, road location, traffic effect and exception contrast; judgments remain open.",
                               "variable_assignments": assignments,
                               "unresolved_judgment_calls": [phrase["phrase"] for phrase in PHRASES],
                               "recording_description": RECORDING,
                               "paired_probe_id": "roadway_stop_alternatives",
                               "deliberate_differences": changed or ["follower_action"],
                               "probe": {"primary_variable": changed[0] if changed else "follower_action",
                                         "comparison_or_standard": "source-bound controlled physical branch contrast",
                                         "target_value_or_branch": case.name}})
    for index, phrase in enumerate(PHRASES):
        cases["sweep_specs"].append({"sweep_id": f"c150640_6272_judgment_{index}",
                                     "target_law_id": LAW,
                                     "judgment_refs": [phrase],
                                     "rationale": "Original site geometry and conflict mechanism must be reviewed before bounding a physical sweep.",
                                     "status": "incomplete",
                                     "missing_inputs": ["Original site-specific route, pass-space and conflict capability measurements are not in frozen inputs."]})
    write(proposal_dir / "cases.json", cases)
    refs = {stage: {"path": "proposals/" + stage + ".json",
                    "sha256": hashlib.sha256((proposal_dir / (stage + ".json")).read_bytes()).hexdigest()}
            for stage in ("relevance_batch", "relevance", "template", "bindings", "cases")}
    refs["judgment_observables"] = [
        {"path": "proposals/" + filename,
         "sha256": hashlib.sha256((proposal_dir / filename).read_bytes()).hexdigest()}
        for filename in judgments]
    write(proposal_dir / "semantic-index.json", {
        "format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT, "stages": refs})


if __name__ == "__main__":
    main()
