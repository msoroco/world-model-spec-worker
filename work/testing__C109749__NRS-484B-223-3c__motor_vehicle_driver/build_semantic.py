"""Write source-faithful draft semantic stages for NRS 484B.223(3)(c)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = "NRS-484B-223-3c"
TEMPLATE = LAW + "@motor_vehicle_driver"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(HERE)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment_path = ROOT / "inputs" / AID / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    quote = assignment["law"]["text"]
    stage_dir = HERE / "proposals"
    channels = [
        ("public_highway_context", "source record", "Source-hashed public highway review and original Native road identity"),
        ("center_turn_lane_design", "source record", "Original map lane topology, markings, bidirectional use and exclusive turning designation"),
        ("turn_completion_event", "frame event", "Original route and body transition into center lane"),
        ("center_lane_body_history", "m", "Original 20 Hz body center and footprint path after turn completion"),
        ("through_lane_merge_event", "frame event", "Original first body transition into receiving through lane"),
        ("receiving_vehicle_history", "frame sequence", "Original receiving actor identity, lane, route and transform"),
        ("frame_and_camera_join", "frame sequence", "Original synchronized four-camera frame and source hash map"),
    ]
    description = {
        "channels": [{"name": name, "unit": unit, "method": method, "sampling_rate_hz": 20,
                      "time_window": "Full original 45-second left-turn, center-lane and merge episode",
                      "reference_frame": "Original Native world frame and 20 Hz frame map",
                      "uncertainty": "Actual lane design, motion, events and body reference need original source review."}
                     for name, unit, method in channels],
        "context_inputs": [
            {"name": "reviewed_highway_and_lane_site", "unit": "source record",
             "method": "Hash-bound original OpenDRIVE and independently reviewed highway and lane dedication"},
            {"name": "reviewed_actor_and_route", "unit": "source record",
             "method": "Hash-bound actor dimensions, entry turn and receiving traffic route"}],
        "limitations": ["49/50/51 feet are requested engineering probes, not measured outcomes.",
                        "A missing merge is censored; it has no invented distance to merge.",
                        "Physical realization and statutory application remain for independent review."]}
    for row in plan["cases"]:
        row["recording_description"] = description
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    relevance = {"cell_id": "C109749", "actor": "motor_vehicle_driver", "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": ["motor_vehicle_driver"],
                                    "relevance_type": "left turn onto highway into shared center turn lane before through-lane merge",
                                    "confidence": "medium",
                                    "notes": "Highway designation, exact lane design and observed merge await original source review."}],
                 "borderline_excluded": []}
    relevance_ref = write(stage_dir / "relevance.json", relevance)
    write(stage_dir / "relevance_batch.json", relevance)
    judgments = [
        ("single center lane to be used only for turning by traffic moving in both directions",
         "Review original highway designation, lane topology, markings and use in both directions.", "center_turn_lane_design"),
        ("after making a left-hand turn onto the highway",
         "Locate observed turn completion from original body and lane history, not controller intent.", "turn_completion_event"),
        ("before merging with traffic",
         "Locate first observed through-lane merge and receiving traffic; absent merge is censored.", "through_lane_merge_event"),
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": "motor_vehicle_driver",
                "status": "draft", "quote": quote,
                "structure": {
                    "law_id": LAW,
                    "activation": {"condition": "A left turn onto a highway with one exclusive shared bidirectional center turn lane is completed in that lane.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Merge with traffic without traveling more than 50 feet in the center turn lane after the left turn.",
                                   "type": "must_not", "numeric_conditions": [{"variable": "post_turn_center_lane_travel", "operator": ">", "value": 50, "unit": "ft"}]},
                    "exceptions": [],
                    "timing": {"description": "Measure original center-lane path from turn completion to the first through-lane merge; censor if no merge is observed.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note, _ in judgments]},
                "parameter_refs": [
                    {"name": "merge_station_target", "kind": "controller", "range_or_domain": "requested 49, 50 or 51 feet after turn; original distance separately measured"},
                    {"name": "merge_observed", "kind": "controller", "range_or_domain": "merge target or no-merge probe"},
                    {"name": "highway_lane_site", "kind": "world_setup", "range_or_domain": "reviewed single exclusive bidirectional center turn lane"}]}
    template_ref = write(stage_dir / "template.json", template)
    judgment_refs = []
    for number, (phrase, note, observable) in enumerate(judgments, 1):
        judgment_refs.append(write(stage_dir / f"judgment-{number}.json", {
            "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {
                "observables": [{"name": observable, "unit": dict((name, unit) for name, unit, _ in channels)[observable], "description": note}],
                "context_inputs": [{"name": "reviewed_highway_and_lane_site", "unit": "source record",
                                    "description": "Retain original map, reviewed public-highway source and lane dedication."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": observable, "unit": dict((name, unit) for name, unit, _ in channels)[observable],
                                     "description": "Keep original 20 Hz frames and source hashes for review."}],
                "limitations": ["Authored route and synthetic fixture do not establish statutory or physical outcome."]}}))
    binding = {"cell_id": "C109749", "actor": "motor_vehicle_driver", "status": "draft",
               "established_contexts": ["left-turn intersection with receiving traffic"],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": x["name"], "kind": x["kind"],
                                        "range_or_domain": x["range_or_domain"], "used_by_laws": [LAW]}
                                       for x in template["parameter_refs"]]}
    binding_ref = write(stage_dir / "bindings.json", binding)
    cases = [{"case_id": AID + "__baseline", "target_law_id": None, "target_type": "baseline", "status": "draft",
              "rationale": "Shared reviewed highway, center lane, actor, receiving route and four-view capture setup.",
              "variable_assignments": {"merge_station_target": {"kind": "controller", "value": 49, "unit": "ft"},
                                       "merge_observed": {"kind": "controller", "value": "merge"},
                                       "highway_lane_site": {"kind": "world_setup", "value": "source_reviewed"}},
              "recording_description": description,
              "unresolved_judgment_calls": [x[0] for x in judgments]}]
    for row in plan["cases"]:
        suffix = row["case_id"].removeprefix(AID + "__")
        target = row["authored_target_distance_ft"]
        cases.append({"case_id": row["case_id"], "target_law_id": LAW,
                      "target_type": "boundary_probe" if target is not None else "judgment_sweep", "status": "draft",
                      "rationale": "Source-bound post-turn travel or no-merge censoring probe; no legal verdict.",
                      "paired_probe_id": "post_turn_center_lane_distance" if target is not None else "merge_observation",
                      "deliberate_differences": ["merge_station_target" if target is not None else "merge_observed"],
                      "variable_assignments": {
                          "merge_station_target": {"kind": "controller", "value": target if target is not None else 49, "unit": "ft"},
                          "merge_observed": {"kind": "controller", "value": "no_merge" if target is None else "merge"},
                          "highway_lane_site": {"kind": "world_setup", "value": "source_reviewed"}},
                      "unresolved_judgment_calls": [x[0] for x in judgments],
                      "recording_description": description,
                      "probe": {"primary_variable": "merge_station_target" if target is not None else "merge_observed",
                                "comparison_or_standard": "Original measured path to first observed merge; no-merge is censored.",
                                "target_value_or_branch": target if target is not None else "no_merge",
                                **({"threshold_ref": "obligation.numeric_conditions[0]", "operator": ">", "unit": "ft", "test_value": target} if target is not None else {})},
                      **({"epsilon_used": {"value": 1, "unit": "ft", "rationale": "Engineering spacing around exact statutory 50-foot boundary."}} if target is not None else {})})
    sweeps = [{"sweep_id": f"c109749-judgment-{i}", "target_law_id": LAW,
               "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete",
               "rationale": "Original highway and Native site review is pending.",
               "missing_inputs": ["reviewed original highway/lane evidence and physical Native observations"]}
              for i, (phrase, note, _) in enumerate(judgments, 1)]
    cases_ref = write(stage_dir / "cases.json", {"cell_id": "C109749", "actor": "motor_vehicle_driver",
                                                "status": "draft", "sweeps_expanded": True,
                                                "cases": cases, "sweep_specs": sweeps})
    write(stage_dir / "semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
         "source": {"path": str(assignment_path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(assignment_path.read_bytes()).hexdigest()},
         "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                    "template": template_ref, "judgment_observables": judgment_refs,
                    "bindings": binding_ref, "cases": cases_ref},
         "status": "draft_local_source_and_physical_review_pending"})

if __name__ == "__main__":
    main()
