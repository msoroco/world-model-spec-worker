"""Source-grounded draft semantic stages for eight C110919 cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "proposals"
SOURCE = ROOT / "inputs" / HERE.name / "assignment.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)), "sha256": sha(path)}


def main():
    assignment = json.loads(SOURCE.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = json.loads((OUT / "cases.json").read_text())
    quote = assignment["law_record"]["text"]
    law = assignment["law_id"]
    actor = assignment["actor"]
    template_id = law + "@" + actor
    expected_cases = [row["case_id"] for row in plan["cases"]]
    if (law != "NRS-484B-307-8a" or assignment["cell_id"] != "C110919" or
            actor != "motor_vehicle_driver" or plan["source_law_text"] != quote or
            [row["case_id"] for row in cases["cases"]] != expected_cases or
            len(expected_cases) != 8 or len(plan["comparisons"]) != 4):
        raise ValueError("Frozen law, scope, eight cases or comparisons changed")
    relevance = {"cell_id": "C110919", "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law, "quote": quote,
                                    "applies_to": [actor], "relevance_type": "direct",
                                    "confidence": "medium",
                                    "notes": "Frozen conditional right-turn witness; exact red-signal, stopping reference, extreme-right position, receiving highway and yield context require original review."}],
                 "borderline_excluded": []}
    relevance_batch_ref = write("relevance-batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    template = {"template_id": template_id, "law_id": law, "actor": actor,
                "quote": quote, "status": "draft",
                "structure": {
                    "activation": {"condition": "steady red signal alone governs approaching vehicular traffic at the intersection",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must",
                                   "description": "Stop before the applicable nearest-side crosswalk/sign/marking reference, or before the intersection when none exists; remain stopped until green unless an applicable exception or permitted post-stop turn applies; yield to signal-directed pedestrians and traffic.",
                                   "numeric_conditions": []},
                    "exceptions": [
                        {"name": "post_stop_right_turn", "source_clause": "After complying with the requirement to stop, vehicular traffic facing such a signal and situated on the extreme right of the highway may proceed into the intersection for a right turn only when the intersecting highway is two-directional or one-way to the right", "replacement_obligation": "yield the right-of-way to pedestrians and other traffic proceeding as directed by the signal"},
                        {"name": "paragraph_c_reference", "source_clause": "except as otherwise provided in paragraphs (c) and (d)", "status": "cross_reference_not_adjudicated_here"},
                        {"name": "paragraph_d_reference", "source_clause": "except as otherwise provided in paragraphs (c) and (d)", "status": "operative_text_not_in_frozen_law_record; preserve unresolved description"}],
                    "timing": {"description": "stop before entering the applicable boundary, remain until green or a separately permitted post-stop turn", "numeric_conditions": []},
                    "judgment_calls_needed": [
                        {"phrase": "situated on the extreme right of the highway", "note": "Measure original full-body lane/highway position; no invented legal lateral cutoff."},
                        {"phrase": "yield the right-of-way", "note": "Retain original pedestrian and traffic paths and temporal precedence; no invented legal time-gap cutoff."}]},
                "parameter_refs": [
                    {"name": "stopping_reference", "kind": "world_setup", "range_or_domain": ["marked_stop_line", "intersection_boundary_without_nearest_side_reference"]},
                    {"name": "observed_signal_schedule", "kind": "world_observation", "range_or_domain": ["steady_red", "red_to_green"]},
                    {"name": "full_body_halt_and_crossing", "kind": "subject_behavior", "range_or_domain": "original Native body and speed history"},
                    {"name": "red_turn_release_policy", "kind": "controller", "range_or_domain": ["after_halt_on_red", "remain_stopped_until_green"]},
                    {"name": "signal_directed_conflict_paths", "kind": "world_observation", "range_or_domain": "original pedestrian and other traffic paths"}]}
    template_ref = write("template.json", template)
    judgments = []
    for slug, phrase, note, observables, limitations in (
        ("extreme-right", "situated on the extreme right of the highway",
         "Original highway/lane geometry and full-body ego footprint must be joined.",
         ["native_body_pose_control", "native_lane_geometry"],
         ["A controller lane label or fabricated lateral tolerance cannot establish legal extreme-right position."]),
        ("right-of-way", "yield the right-of-way",
         "Original signal-directed participant trajectories and ego entry order must be reviewed.",
         ["native_body_pose_control", "native_pedestrian_paths", "native_other_traffic_paths", "signal_state_observed"],
         ["A synthetic conflict-clearance gap or numeric cutoff is an engineering check, not a legal verdict."])):
        judgment = {"template_id": template_id, "phrase": phrase, "note": note,
                    "status": "draft", "observable_requirements": {
                        "observables": [{"name": name, "unit": "structured",
                                         "description": "Original Native source joined to complete frame history"}
                                        for name in observables],
                        "context_inputs": [{"name": "surveyed_C110919_intersection",
                                            "unit": "structured",
                                            "description": "Original map, official signal and road controls"}],
                        "sweep_dimensions": [], "landmarks": [],
                        "recording_needs": [{"name": "four_source_cameras", "unit": "video",
                                             "description": "Original all-frame pixel review for signal, body and participant visibility"}],
                        "limitations": limitations}}
        judgments.append(write("judgment-" + slug + ".json", judgment))
    bindings = {"cell_id": "C110919", "actor": actor, "status": "draft",
                "established_contexts": ["Authored right-turn intersection; original public-highway, signal direction, receiving-road and participant context remain unverified"],
                "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
                "context_refs": [],
                "fixed_parameters": [
                    {"name": "actor_and_maneuver", "value": "motor_vehicle_driver_right_turn", "rationale": "Frozen C110919 right-turn scope"},
                    {"name": "capture_rate_hz", "value": 20, "rationale": "Four-camera 480-frame Native capture contract"},
                    {"name": "receiving_highway", "value": "two_directional_authored", "rationale": "Original map direction and roadway classification require review"}],
                "variable_parameters": [
                    {"name": "halt_before_nearest_boundary", "kind": "subject_behavior", "range_or_domain": [True, False], "used_by_laws": [law]},
                    {"name": "halt_before_intersection_when_no_crosswalk_sign_or_marking", "kind": "subject_behavior", "range_or_domain": [True, False], "used_by_laws": [law]},
                    {"name": "remain_stopped_until_green", "kind": "subject_behavior", "range_or_domain": [True, False], "used_by_laws": [law]},
                    {"name": "pedestrian_conflict_response", "kind": "controller", "range_or_domain": ["yield_wait", "yield_conflict_entry"], "used_by_laws": [law]}]}
    bindings_ref = write("bindings.json", bindings)
    cases_ref = {"path": "proposals/cases.json", "sha256": sha(OUT / "cases.json")}
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
             "status": "draft_not_delivery_selected",
             "stages": {"relevance_batch": relevance_batch_ref, "relevance": relevance_ref,
                        "template": template_ref, "judgment_observables": judgments,
                        "bindings": bindings_ref, "cases": cases_ref}}
    path = OUT / "semantic-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"cases": len(expected_cases), "comparisons": 4,
                      "stages": 7, "semantic_index_sha256": sha(path),
                      "canonical_selected": False}))


if __name__ == "__main__":
    main()
