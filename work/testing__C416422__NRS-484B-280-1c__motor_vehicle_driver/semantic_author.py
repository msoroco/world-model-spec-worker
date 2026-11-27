"""Draft canonical semantic stages for the selected near-road branch."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((ROOT / "assignment.json").read_text())
LAW_ID, CELL, ACTOR = (ASSIGNMENT[key] for key in ("law_id", "cell_id", "actor"))
LAW = ASSIGNMENT["law"]["text"]
TEMPLATE = LAW_ID + "@" + ACTOR


def write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def named(name, description):
    return {"name": name, "unit": "structured record", "description": description}


def main():
    refs = {}
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW_ID, "quote": LAW, "applies_to": [ACTOR],
                                    "relevance_type": "direct near-road pedestrian caution encounter",
                                    "confidence": "high",
                                    "notes": "Supplemental C416422 branch selects a pedestrian bodily off road on an adjacent reviewed sidewalk."}],
                 "borderline_excluded": []}
    for stage in ("relevance_batch", "relevance"):
        refs[stage] = write(stage + ".json", relevance)
    judgment = {"phrase": "Exercise proper caution upon observing a pedestrian",
                "note": "No numeric legal caution, response-delay or near-distance cutoff is supplied."}
    parameters = [{"name": "response_policy", "kind": "controller",
                   "range_or_domain": "prompt or deferred engineering brake after scripted-driver observation input"}]
    refs["template"] = write("template.json", {"template_id": TEMPLATE, "law_id": LAW_ID,
        "actor": ACTOR, "quote": LAW,
        "structure": {"law_id": LAW_ID,
                      "activation": {"condition": "Motor-vehicle driver receives an original scripted observation input for a pedestrian bodily off road on an adjacent sidewalk; statutory near remains for review.",
                                     "numeric_conditions": []},
                      "obligation": {"description": "Exercise proper caution upon observing the pedestrian.",
                                     "type": "must", "numeric_conditions": []},
                      "exceptions": [],
                      "timing": {"description": "Original observation-input and response history over roadside encounter frames.",
                                 "numeric_conditions": []},
                      "judgment_calls_needed": [judgment]},
        "parameter_refs": parameters})
    observations = [named("ego_body_history", "Original motor-vehicle body and route history."),
                    named("pedestrian_body_history", "Separate original pedestrian body and off-road sidewalk route."),
                    named("ego_speed_and_brake_history", "Original speed and braking commands."),
                    named("driver_observation_input_history", "Instrumented scripted-driver observation input, distinct from visibility or cognition."),
                    named("road_boundary_context", "Original reviewed road edge, sidewalk lane and adjacency context."),
                    named("participant_classification_context", "Original motor-vehicle driver and pedestrian classification sources."),
                    named("contact_events", "Original contact sensor event history."),
                    named("camera_frame_map", "Original synchronized four-camera identities.")]
    contexts = [named("road_site_context", "Original OpenDRIVE and Native road classification, edges and sidewalk review."),
                named("driver_input_context", "Scripted driver-control input source; human observation remains unresolved.")]
    refs["judgment_observables"] = [write("judgment-1.json", {"template_id": TEMPLATE,
        "phrase": judgment["phrase"], "note": judgment["note"], "status": "draft",
        "observable_requirements": {"observables": observations, "context_inputs": contexts,
            "sweep_dimensions": [{"name": "response_policy", "unit": "categorical",
                                  "description": "Prompt versus deferred engineering braking; no legal cutoff."}],
            "landmarks": [], "recording_needs": observations,
            "limitations": ["Scripted input does not prove human cognition.",
                            "Road-edge gap does not define statutory near; response delay does not decide proper caution."]}})]
    refs["bindings"] = write("bindings.json", {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["single lane per direction", "adjacent reviewed sidewalk", "motor-vehicle travel", "pedestrian bodily off road"],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW_ID]) for item in parameters]})
    channels = [{"name": item["name"], "unit": item["unit"], "sampling_rate_hz": 20,
                 "method": item["description"], "time_window": "approach through pedestrian clearance",
                 "reference_frame": "CARLA world with original frame and time",
                 "uncertainty": "20 Hz sampling and simulator body precision"} for item in observations]
    recording = {"channels": channels,
                 "context_inputs": [{"name": item["name"], "unit": item["unit"],
                                     "method": item["description"]} for item in contexts],
                 "limitations": ["Native road/pedestrian motion and camera pixels require physical verification.",
                                 "Human observation, statutory near and legal proper caution remain unresolved."]}
    cases = [{"case_id": ROOT.name + "__baseline", "target_law_id": None,
              "target_type": "baseline",
              "rationale": "Shared road, participant identities, routes and instrumented input baseline.",
              "variable_assignments": {"response_policy": {"kind": "controller",
                  "value": "prompt_brake", "note": "Reference engineering controller only."}},
              "recording_description": recording,
              "unresolved_judgment_calls": [judgment["phrase"]]}]
    for suffix in ("prompt_brake", "deferred_brake"):
        cases.append({"case_id": ROOT.name + "__" + suffix, "target_law_id": LAW_ID,
            "target_type": "boundary_probe",
            "rationale": "Controlled engineering response timing to the same off-road sidewalk pedestrian encounter.",
            "variable_assignments": {"response_policy": {"kind": "controller", "value": suffix,
                "note": "Scripted driver input and brake response, not a legal cutoff."}},
            "recording_description": recording,
            "unresolved_judgment_calls": [judgment["phrase"]],
            "paired_probe_id": ROOT.name + "__response_pair",
            "deliberate_differences": ["response_policy"],
            "probe": {"primary_variable": "response_policy",
                      "comparison_or_standard": "Original response timing, body gap and contact; legal caution unresolved.",
                      "target_value_or_branch": suffix}})
    refs["cases"] = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
        "status": "draft", "cases": cases,
        "sweep_specs": [{"sweep_id": "c416422-response", "target_law_id": LAW_ID,
                         "judgment_refs": [judgment], "status": "incomplete",
                         "rationale": "Original nontransient encounter range and human-observation status require physical source review.",
                         "missing_inputs": ["Source-backed Native sidewalk and off-road encounter with driver input history",
                                            "Feasible nontransient response range without a legal cutoff"]}],
        "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                   "assignment_id": ROOT.name, "stages": refs})


if __name__ == "__main__":
    main()
