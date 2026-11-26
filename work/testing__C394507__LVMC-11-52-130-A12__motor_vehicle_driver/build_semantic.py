"""Author exact LVMC crosswalk semantic proposals without legal labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "LVMC-11-52-130-A12"
CELL = "C394507"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
QUOTE = ("No person shall stop, stand or park a vehicle except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device, in any of the following places: Within twenty feet of any marked crosswalk.")
JUDGMENTS = (
    ("stop, stand or park", "Original purpose, service and motion history require independent activity classification."),
    ("necessary to avoid conflict with other traffic", "Original traffic trajectories and necessity require source review."),
    ("in compliance with law or the directions of a police officer or a traffic control device", "Applicable law and actual direction authority require source review."),
)


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    description = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())[
        "recording_description"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
                           "applies_to": [ACTOR],
                           "relevance_type": "vehicle stop, stand or park within twenty feet of marked crosswalk",
                           "confidence": "medium",
                           "notes": "Actual jurisdiction, marking, person, activity and exception remain source-gated."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    template = {"template_id": TEMPLATE, "law_id": LAW,
                "actor": ACTOR, "quote": QUOTE,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "A person stops, stands or parks a vehicle near a marked crosswalk.",
                                   "numeric_conditions": [{"variable": "body_clearance_ft_arithmetic",
                                                           "operator": "within",
                                                           "value": 20, "unit": "feet"}]},
                    "obligation": {"description": "Do not stop, stand or park a vehicle within twenty feet of any marked crosswalk unless an exact exception applies.",
                                   "type": "must_not", "numeric_conditions": []},
                    "exceptions": [
                        {"source_clause": "except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device",
                         "trigger": "Necessary avoidance of traffic conflict in compliance with law or applicable officer/device directions",
                         "effect": "The stated exception may apply after source review",
                         "replacement_obligation": "Assess the source-supported exception without automatic legal classification"}],
                    "timing": {"description": "Observe original approach, stationary/service interval and crossing context.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for phrase, note in JUDGMENTS]},
                "parameter_refs": [
                    {"name": "body_clearance_target_m", "kind": "world_setup",
                     "range_or_domain": "5.9, 6.096 or 6.3 m requested engineering target"},
                    {"name": "requested_activity", "kind": "controller",
                     "range_or_domain": "destination stop, stand, park, necessary or directed halt"},
                    {"name": "requested_exception", "kind": "world_setup",
                     "range_or_domain": "none, traffic conflict, police or device direction"},
                    {"name": "crosswalk_marked", "kind": "world_setup",
                     "range_or_domain": "marked or unmarked comparative reference"}]}
    refs["template"] = write("template.json", template)
    observable_refs = []
    for index, (phrase, note) in enumerate(JUDGMENTS, 1):
        item = {"template_id": TEMPLATE, "phrase": phrase, "note": note,
                "status": "draft", "observable_requirements": {
                    "observables": [
                        {"name": "original_body_polygon", "unit": "structured",
                         "description": "Original 20 Hz full vehicle body relative to crossing extent."},
                        {"name": "original_speed", "unit": "structured",
                         "description": "Original 20 Hz motion history without legal duration threshold."},
                        {"name": "activity_readback", "unit": "structured",
                         "description": "Original service/activity readback and source context."},
                        {"name": "exception_readback", "unit": "structured",
                         "description": "Original traffic and direction context readback."},
                        {"name": "four_camera_frames", "unit": "structured",
                         "description": "Four original synchronized camera source identities."}],
                    "context_inputs": [{"name": "jurisdiction_and_crossing_context",
                                        "unit": "source",
                                        "description": "Reviewed jurisdiction, markings, vehicle/person and exception source packets."}],
                    "sweep_dimensions": [], "landmarks": [],
                    "recording_needs": [
                        {"name": "jurisdiction_and_crossing_context", "unit": "source",
                         "description": "Original reviewed site and independent context source records."}],
                    "limitations": [note, "CPU fixture cannot establish physical or legal status."]}}
        observable_refs.append(write(f"judgment-{index}.json", item))
    refs["judgment_observables"] = observable_refs
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen marked-crosswalk stop/stand cell; original site and law application pending review."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "reviewed_crosswalk_site",
                              "value": "source_packet_pending",
                              "rationale": "Hold jurisdiction, map, person, vehicle and crossing geometry fixed across linked comparisons."}],
        "variable_parameters": [
            {"name": "body_clearance_target_m", "kind": "world_setup",
             "range_or_domain": "5.9, 6.096, 6.3 m", "used_by_laws": [LAW]},
            {"name": "requested_activity", "kind": "controller",
             "range_or_domain": "destination_stop, destination_stand, destination_park, necessary_halt, directed_halt",
             "used_by_laws": [LAW]},
            {"name": "requested_exception", "kind": "world_setup",
             "range_or_domain": "none, traffic_conflict, police_direction, device_direction",
             "used_by_laws": [LAW]},
            {"name": "crosswalk_marked", "kind": "world_setup",
             "range_or_domain": "true or false", "used_by_laws": [LAW]}]}
    refs["bindings"] = write("bindings.json", binding)
    base_values = {"body_clearance_target_m": {"kind": "world_setup", "value": 5.9},
                   "requested_activity": {"kind": "controller", "value": "destination_stop"},
                   "requested_exception": {"kind": "world_setup", "value": "none"},
                   "crosswalk_marked": {"kind": "world_setup", "value": True}}
    baseline = {"case_id": AID + "__baseline", "target_law_id": LAW,
                "target_type": "baseline", "rationale": "Shared reviewed marked-crosswalk destination-halt reference.",
                "recording_description": description,
                "unresolved_judgment_calls": [phrase for phrase, _ in JUDGMENTS],
                "variable_assignments": base_values,
                "paired_probe_id": "crosswalk_clearance_boundary",
                "deliberate_differences": [],
                "probe": {"primary_variable": "body_clearance_target_m",
                          "comparison_or_standard": "source-measured body clearance to reviewed crossing polygon",
                          "target_value_or_branch": 5.9}}
    cases = [baseline]
    for item in plan["cases"]:
        case_id = item["case_id"]
        tag = item["variant"]
        values = {"body_clearance_target_m": {"kind": "world_setup",
                                               "value": float(item["body_clearance_target"].removesuffix("m"))},
                  "requested_activity": {"kind": "controller",
                                         "value": item["halt_activity_request"]},
                  "requested_exception": {"kind": "world_setup",
                                          "value": item["exception_request"]},
                  "crosswalk_marked": {"kind": "world_setup",
                                       "value": item["crosswalk_marking_request"] == "marked"}}
        threshold_case = tag in ("destination_inside_20ft", "destination_exact_20ft",
                                 "destination_outside_20ft")
        differences = [name for name in values if values[name] != base_values[name]]
        if not differences:
            differences = ["body_clearance_target_m"]
        primary = differences[0]
        probe = {"primary_variable": primary,
                 "comparison_or_standard": "independent source-measured geometry, activity and exception context",
                 "target_value_or_branch": values[primary]["value"]}
        if threshold_case:
            probe.update(threshold_ref="activation.numeric_conditions[0]",
                         operator="within", unit="feet",
                         test_value=values["body_clearance_target_m"]["value"] / .3048)
        cases.append({"case_id": case_id, "target_law_id": LAW,
            "target_type": "boundary_probe", "paired_probe_id": "crosswalk_clearance_boundary" if threshold_case else tag,
            "rationale": "Source-measure requested crosswalk distance, activity and exception variant without assigning a legal outcome.",
            "recording_description": description,
            "variable_assignments": values,
            "unresolved_judgment_calls": [phrase for phrase, _ in JUDGMENTS],
            "deliberate_differences": differences, "probe": probe,
            "epsilon_used": .001 if threshold_case else "qualitative control"})
    sweeps = [{"sweep_id": f"source_review_{index}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}],
               "status": "incomplete",
               "rationale": "Original physical and legal context not supplied to worker; preserve source-gated judgment.",
               "missing_inputs": ["Reviewed original Native service, traffic, applicable-law and direction source packet"]}
              for index, (phrase, note) in enumerate(JUDGMENTS, 1)]
    refs["cases"] = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
                                          "status": "draft", "cases": cases,
                                          "sweep_specs": sweeps,
                                          "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "source": "Exact LVMC 11.52.130(A)(12) text and frozen C394507 cell",
                                  "status": "draft", "stages": refs})


if __name__ == "__main__":
    main()
