"""Draft original-law semantic stages for the supplemental transit branch."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
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
                                    "relevance_type": "direct transit-stop pedestrian caution encounter",
                                    "confidence": "high",
                                    "notes": "Selected branch varies waiting at stop versus movement toward public bus ingress; legal boarding remains unresolved."}],
                 "borderline_excluded": []}
    for stage in ("relevance_batch", "relevance"):
        refs[stage] = write(stage + ".json", relevance)
    judgment = {"phrase": "Exercise proper caution upon observing a pedestrian",
                "note": "No numeric legal caution, near-stop, boarding or response-time cutoff is supplied."}
    parameters = [{"name": "passenger_route_plan", "kind": "world_setup",
                   "range_or_domain": "waiting at stop or moving toward bus-side ingress"}]
    refs["template"] = write("template.json", {"template_id": TEMPLATE,
        "law_id": LAW_ID, "actor": ACTOR, "quote": LAW,
        "structure": {"law_id": LAW_ID,
            "activation": {"condition": "Motor-vehicle driver observes a pedestrian at or near a bus stop, bench, shelter or transit stop, or in the act of boarding public transportation; selected physical bus stop and public bus.",
                           "numeric_conditions": []},
            "obligation": {"description": "Exercise proper caution upon observing the pedestrian.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Original scripted input and response over transit-stop encounter frames.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [judgment]},
        "parameter_refs": parameters})
    descriptions = {
        "ego_body_history": "Original motor-vehicle body and route history.",
        "pedestrian_body_history": "Original pedestrian body and stop-to-bus motion history.",
        "bus_body_history": "Original public-bus body and placement readback.",
        "ego_speed_and_brake_history": "Original speed and braking commands.",
        "driver_observation_input_history": "Instrumented scripted-driver observation input, distinct from human cognition.",
        "passenger_phase_history": "Requested waiting or boarding-approach state with measured original body motion.",
        "transit_stop_context": "Original physical bus-stop prop identity and placement.",
        "bus_door_region_gap_history": "Distance to engineering bus-side ingress proxy, not a verified actual door.",
        "contact_events": "Original contact sensor event history.",
        "camera_frame_map": "Original synchronized four-camera identities."}
    observations = [named(name, description) for name, description in descriptions.items()]
    contexts = [named("transit_site_context", "Original OpenDRIVE, stop prop, bus actor, body and side region."),
                named("driver_input_context", "Scripted driver input; human observation unresolved.")]
    refs["judgment_observables"] = [write("judgment-1.json", {"template_id": TEMPLATE,
        "phrase": judgment["phrase"], "note": judgment["note"], "status": "draft",
        "observable_requirements": {"observables": observations, "context_inputs": contexts,
            "sweep_dimensions": [{"name": "passenger_route_plan", "unit": "categorical",
                                  "description": "Waiting at stop versus bus-side approach; no legal cutoff."}],
            "landmarks": [], "recording_needs": observations,
            "limitations": ["Bus-side region is an engineering proxy; actual door and boarding need pixel review.",
                            "Scripted input does not prove human cognition or legal proper caution."]}})]
    refs["bindings"] = write("bindings.json", {"cell_id": CELL, "actor": ACTOR,
        "status": "draft", "established_contexts": ["road travel", "physical bus stop", "public bus", "pedestrian"],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW_ID]) for item in parameters]})
    recording = {"channels": [{"name": item["name"], "unit": item["unit"],
        "sampling_rate_hz": 20, "method": item["description"],
        "time_window": "approach through transit-stop encounter",
        "reference_frame": "CARLA world with original frame and time",
        "uncertainty": "20 Hz sampling and simulator body precision"} for item in observations],
        "context_inputs": [{"name": item["name"], "unit": item["unit"],
                            "method": item["description"]} for item in contexts],
        "limitations": ["Actual stop, bus, door, passenger motion and four-camera pixels require physical review.",
                        "Human observation and statutory proper caution remain unresolved."]}
    cases = [{"case_id": ROOT.name + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared physical stop, bus, motorist and pedestrian setup.",
              "variable_assignments": {"passenger_route_plan": {"kind": "world_setup", "value": "waiting_at_stop"}},
              "recording_description": recording,
              "unresolved_judgment_calls": [judgment["phrase"]]}]
    for phase in ("waiting_at_stop", "boarding_bus"):
        cases.append({"case_id": ROOT.name + "__" + phase, "target_law_id": LAW_ID,
            "target_type": "boundary_probe",
            "rationale": "Controlled passenger state at the same stop; engineering comparison only.",
            "variable_assignments": {"passenger_route_plan": {"kind": "world_setup", "value": phase,
                "note": "Original movement and actual bus door need independent review."}},
            "recording_description": recording,
            "unresolved_judgment_calls": [judgment["phrase"]],
            "paired_probe_id": ROOT.name + "__passenger_state_pair",
            "deliberate_differences": ["passenger_route_plan"],
            "probe": {"primary_variable": "passenger_route_plan",
                      "comparison_or_standard": "Original pedestrian stop distance and bus-side movement; legal caution unresolved.",
                      "target_value_or_branch": phase}})
    refs["cases"] = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
        "status": "draft", "cases": cases,
        "sweep_specs": [{"sweep_id": "c394554-transit-passenger-state", "target_law_id": LAW_ID,
                         "judgment_refs": [judgment], "status": "incomplete",
                         "rationale": "Original nontransient stop/boarding and human-observation range require physical source review.",
                         "missing_inputs": ["Original physical bus stop, public bus and visible pedestrian ingress",
                                            "Nontransient response range without legal cutoff"]}],
        "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                   "assignment_id": ROOT.name, "stages": refs})


if __name__ == "__main__":
    main()
