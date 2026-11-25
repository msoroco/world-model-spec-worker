"""Author the exact flashing-yellow-arrow semantic stage proposal chain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = "NRS-484B-307-7a"
ACTOR = "motor_vehicle_driver"
PLAN = json.loads((HERE / "case-plan.json").read_text())
QUOTE = PLAN["law_text"]
OUT = HERE / "proposals"


def write(name, payload):
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def named(name, description):
    return {"name": name, "unit": "structured record", "description": description}


def build():
    OUT.mkdir(exist_ok=True)
    relevance = {"cell_id": "C111610", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": [ACTOR], "relevance_type": "direct official flashing-yellow-turn-arrow driver duty",
            "confidence": "high", "notes": "Frozen selected driver faces a turn arrow at an intersection."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    phrases = [
        "cautiously enter the intersection",
        "other such movement as is permitted by other signal indications displayed at the same time",
        "yield the right-of-way to pedestrians lawfully within the intersection or an adjacent crosswalk",
        "yield the right-of-way to other traffic lawfully within the intersection",
    ]
    notes = [
        "Caution has no numeric cutoff in the exact law.",
        "The contemporaneous other official indication and its governed movement require original source review.",
        "Lawful presence and right of way require original pedestrian entry and movement context; no numeric cutoff is supplied.",
        "Lawful traffic presence and right of way require original entry and movement context; no numeric cutoff is supplied.",
    ]
    variables = [
        ("pedestrian_region", "world_setup", "absent, adjacent crosswalk, or intersection"),
        ("other_traffic_region", "world_setup", "absent or intersection"),
        ("concurrent_indication", "world_setup", "absent or externally sourced contemporaneous indication"),
        ("selected_movement_route", "world_setup", "surveyed arrow turn or separately surveyed permitted movement"),
        ("commanded_turn_path", "controller", "source-gated route attempt, not a legal outcome"),
    ]
    template_id = LAW + "@" + ACTOR
    template = {"template_id": template_id, "law_id": LAW, "actor": ACTOR,
        "quote": QUOTE,
        "structure": {"law_id": LAW,
            "activation": {"condition": "An official flashing yellow turn arrow faces vehicular traffic, alone or with another signal.", "numeric_conditions": []},
            "obligation": {"description": "Cautious intersection entry for the indicated or concurrently permitted movement, yielding to lawfully present pedestrians and traffic in their stated regions.", "type": "must", "numeric_conditions": []},
            "exceptions": [{"trigger": "Another indication displayed at the same time permits another movement.",
                "effect": "That movement may also be made.",
                "replacement_obligation": "Preserve cautious entry and the pedestrian and traffic yield duties.",
                "source_clause": "or other such movement as is permitted by other signal indications displayed at the same time"}],
            "timing": {"description": "Original arrow on/off phases, concurrent display, participant entry and ego movement joined by Native frame.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note in zip(phrases, notes)]},
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain} for name, kind, domain in variables]}
    refs["template"] = write("template.json", template)
    obs = [named("ego_body_heading_history", "Original ego body, speed, brake and heading by frame."),
           named("facing_arrow_history", "Original official head identity, facing relation and flashing phase by frame."),
           named("pedestrian_body_lawful_history", "Original pedestrian body, entry context and region by frame."),
           named("other_traffic_history", "Original other traffic body, entry context and region by frame."),
           named("concurrent_indication_history", "Original concurrent indication identity and displayed phase by frame."),
           named("turn_route", "Original ego route and measured movement by frame."),
           named("camera_frame_map", "Four synchronized original camera frame identities.")]
    contexts = [named("intersection_context", "Surveyed map, facing head and approach source identities."),
                named("pedestrian_entry_context", "Original pedestrian entry and applicable indication context."),
                named("traffic_entry_context", "Original other traffic entry and applicable indication context."),
                named("signal_controller_context", "Official arrow and concurrent controller source identities."),
                named("route_source_context", "Surveyed arrow and any alternate movement route sources.")]
    refs["judgment_observables"] = []
    for i, (phrase, note) in enumerate(zip(phrases, notes), 1):
        value = {"template_id": template_id, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {"observables": obs, "context_inputs": contexts,
                "sweep_dimensions": [], "landmarks": [], "recording_needs": obs,
                "limitations": ["No legal predicate or cutoff is supplied by this proposal.",
                                "Official signal, lawful presence, cautious entry and physical sight lines require independent original-source review."]}}
        refs["judgment_observables"].append(write(f"judgment-{i}.json", value))
    binding = {"cell_id": "C111610", "actor": ACTOR, "status": "draft",
        "established_contexts": ["intersection", "turn", "pedestrian"],
        "law_refs": [{"template_id": template_id, "binding_kind": "direct"}], "context_refs": [],
        "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind, "range_or_domain": domain,
                                 "used_by_laws": [LAW]} for name, kind, domain in variables]}
    refs["bindings"] = write("bindings.json", binding)
    channels = [{"name": o["name"], "unit": o["unit"], "sampling_rate_hz": 20,
                 "method": o["description"], "time_window": "approach through intersection clearance",
                 "reference_frame": "original Native frame and time", "uncertainty": "20 Hz sampling and Native source precision"} for o in obs]
    context_records = [{"name": c["name"], "unit": c["unit"], "method": c["description"]} for c in contexts]
    description = {"channels": channels, "context_inputs": context_records,
        "limitations": ["Physical signal, actor and camera realization need original Native review.",
                        "Legal right of way, lawful presence and cautiousness remain unresolved."]}
    values = {"pedestrian_region": "absent", "other_traffic_region": "absent",
              "concurrent_indication": "absent", "selected_movement_route": "surveyed_arrow_turn",
              "commanded_turn_path": "source_gated_arrow_route"}
    def case(case_id, target, difference):
        assignments = {name: {"kind": kind, "value": values[name],
                              "note": "Selected physical setup; no legal verdict."} for name, kind, _ in variables}
        if target == "arrow_ped_crosswalk": assignments["pedestrian_region"]["value"] = "adjacent_crosswalk"
        if target == "arrow_ped_intersection": assignments["pedestrian_region"]["value"] = "intersection"
        if target == "arrow_vehicle_intersection": assignments["other_traffic_region"]["value"] = "intersection"
        if target == "arrow_concurrent_movement":
            assignments["concurrent_indication"]["value"] = "reviewed_contemporaneous_movement_indication"
            assignments["selected_movement_route"]["value"] = "separate_surveyed_through_route"
        baseline = target == "baseline"
        result = {"case_id": case_id, "target_law_id": None if baseline else LAW,
                  "target_type": "baseline" if baseline else "boundary_probe",
                  "rationale": "Reference arrow and intersection setup." if baseline else next(c["description"] for c in PLAN["cases"] if c["case_suffix"] == target),
                  "variable_assignments": assignments, "recording_description": description,
                  "unresolved_judgment_calls": phrases}
        if not baseline:
            result.update(paired_probe_id="arrow-" + target,
                          deliberate_differences=difference,
                          probe={"primary_variable": difference[0],
                                 "comparison_or_standard": "same-site arrow-clear reference",
                                 "target_value_or_branch": target})
        return result
    selected = [("arrow_clear", ["pedestrian_region"]),
                ("arrow_ped_crosswalk", ["pedestrian_region"]),
                ("arrow_ped_intersection", ["pedestrian_region"]),
                ("arrow_vehicle_intersection", ["other_traffic_region"]),
                ("arrow_concurrent_movement", ["concurrent_indication", "selected_movement_route"])]
    cases = [case(AID + "__baseline", "baseline", [])]
    cases += [case(AID + "__" + suffix, suffix, diff) for suffix, diff in selected]
    sweeps = [{"sweep_id": f"c111610-arrow-judgment-{i}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}],
               "status": "incomplete", "rationale": "A source-backed physical sweep range cannot yet be fixed from the exported site and official indication inventory.",
               "missing_inputs": ["Reviewed original official flashing-arrow and concurrent indication source",
                                  "Surveyed C111610 physical route, pedestrian and other-traffic timing feasibility ranges"]}
              for i, (phrase, note) in enumerate(zip(phrases, notes), 1)]
    refs["cases"] = write("cases.json", {"cell_id": "C111610", "actor": ACTOR,
                                            "status": "draft", "cases": cases,
                                            "sweep_specs": sweeps, "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                   "assignment_id": AID, "stages": refs})
    print("authored", len(cases)-1, "selected exact semantic cases and", len(phrases), "judgment contracts")


if __name__ == "__main__":
    build()
