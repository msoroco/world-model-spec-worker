"""Author source-bound canonical proposals for the selected qualitative law cases."""

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
PROPOSALS = ROOT / "proposals"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / (path.name + ".semantic-stage")
    stage.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    os.replace(stage, path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "selected-preflight-manifest.json").read_text())
    aid, law_id, cell_id, actor = (plan[k] for k in
                                   ("assignment_id", "law_id", "cell_id", "actor"))
    quote = plan["source_law"]["text"]
    template_id = law_id + "@" + actor
    common = {"cell_id": cell_id, "actor": actor, "status": "draft"}
    relevance = dict(common, relevant_laws=[{
        "law_id": law_id, "quote": quote, "applies_to": [actor],
        "relevance_type": "specific_match", "confidence": "high",
        "notes": "Frozen road/travel/pedestrian cell matches the motor-vehicle driver clause; all statutory positions require separate source review."
    }], borderline_excluded=[])
    write(PROPOSALS / "relevance-batch.json", relevance)
    write(PROPOSALS / "relevance.json", relevance)

    judgments = [
        {"phrase": "upon observing a pedestrian", "note": "Actual driver observation requires original driver-view and independent source review; camera visibility and requested control do not prove perception."},
        {"phrase": "proper caution", "note": "The qualitative legal standard requires later independent judgment; requested speed and diagnostic motion are raw evidence only."},
    ]
    template = {"template_id": template_id, "law_id": law_id, "actor": actor,
                "status": "draft", "quote": quote,
                "structure": {"law_id": law_id,
                              "activation": {"condition": "Driver observes a pedestrian in one of the stated statutory positions.", "numeric_conditions": []},
                              "obligation": {"type": "must", "description": "Exercise proper caution upon observing that pedestrian.", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Upon observing the pedestrian; no numeric duration is stated.", "numeric_conditions": []},
                              "judgment_calls_needed": judgments},
                "parameter_refs": []}
    write(PROPOSALS / "template.json", template)
    judgment_refs = []
    for number, judgment in enumerate(judgments, 1):
        requirements = {
            "observables": [{"name": "native_vehicle_pedestrian_pose_and_control", "unit": "structured", "description": "Original synchronized vehicle and pedestrian transforms, motion, and requested control."}],
            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": "native_vehicle_pedestrian_pose_and_control", "unit": "structured", "description": "Original source-joined participant motion and controls."},
                                {"name": "four_camera_video", "unit": "structured", "description": "Original synchronized camera pixels for independent review."}],
            "limitations": ["Original driver perception cannot be inferred from camera visibility or controller request.",
                            "The statutory position and proper caution require independent source review; no numeric legal threshold is supplied."]}
        result = {"template_id": template_id, "phrase": judgment["phrase"],
                  "note": judgment["note"], "status": "draft",
                  "observable_requirements": requirements}
        path = PROPOSALS / f"judgment-{number}.json"
        write(path, result)
        judgment_refs.append(path)

    variables = [
        {"name": "statutory_position_branch", "kind": "world_setup",
         "range_or_domain": "One of the eleven separately sourced statutory position alternatives",
         "used_by_laws": [law_id]},
        {"name": "post_observation_ego_speed_request", "kind": "controller",
         "range_or_domain": "caution or maintain requested-control policy; no legal outcome implied",
         "used_by_laws": [law_id]},
        {"name": "observed_driver_perception", "kind": "subject_behavior",
         "range_or_domain": "original independently reviewed observation or unknown",
         "used_by_laws": [law_id]},
        {"name": "ego_speed", "kind": "subject_behavior",
         "range_or_domain": "original measured vehicle speed in m/s or unknown",
         "used_by_laws": [law_id]},
    ]
    binding = dict(common, established_contexts=[{
        "name": "road_travel_pedestrian", "source": "Frozen C230266 catalog cell; actual pedestrian position and observation remain subject to source review."
    }], law_refs=[{"template_id": template_id, "binding_kind": "direct"}],
                   context_refs=[], fixed_parameters=[], variable_parameters=variables)
    write(PROPOSALS / "bindings.json", binding)

    def assignment(branch, request):
        return {
            "statutory_position_branch": {"kind": "world_setup", "value": branch, "unit": "categorical"},
            "post_observation_ego_speed_request": {"kind": "controller", "value": request, "unit": "categorical"},
            "observed_driver_perception": {"kind": "subject_behavior", "value": None, "unit": "categorical"},
            "ego_speed": {"kind": "subject_behavior", "value": None, "unit": "m/s"},
        }

    baseline_recording = json.loads((ROOT / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    cases = [dict(common, case_id=aid + "__baseline", target_law_id=None,
                  target_type="baseline", rationale="Unselected neutral comparison definition; no original recording or observation asserted.",
                  variable_assignments=assignment("neutral", "maintain"),
                  unresolved_judgment_calls=[], recording_description=baseline_recording)]
    for entry in manifest["cases"]:
        construction = json.loads((ROOT / entry["construction"]).read_text())
        case_id = entry["case_id"]
        branch = construction.get("source_position_branch") or case_id.rsplit("__", 1)[-1].rsplit("_", 1)[0]
        suffix = case_id.rsplit("__", 1)[-1]
        request = "caution" if suffix.endswith("_caution") or suffix == "probe_1" else "maintain"
        group = "road" if suffix.startswith("probe_") else suffix.rsplit("_", 1)[0]
        cases.append({"case_id": case_id, "target_law_id": law_id,
                      "target_type": "judgment_sweep",
                      "rationale": "Fixed statutory-position construction and requested-control contrast; original observation, physical outcome, and legal judgment remain unverified.",
                      "paired_probe_id": group + "_requested_control_pair",
                      "deliberate_differences": ["post_observation_ego_speed_request"],
                      "probe": {"primary_variable": "post_observation_ego_speed_request",
                                "comparison_or_standard": "same-position requested-control contrast; not a legal threshold",
                                "target_value_or_branch": request},
                      "variable_assignments": assignment(group, request),
                      "unresolved_judgment_calls": [j["phrase"] for j in judgments],
                      "recording_description": construction["recording_description"]})
    sweep = {"sweep_id": "proper_caution_source_review", "target_law_id": law_id,
             "judgment_refs": judgments, "status": "incomplete",
             "rationale": "Original driver observation and the qualitative proper-caution standard are not fixed by a controller speed contrast; physical sweep coverage remains to be authored without a legal cutoff.",
             "missing_inputs": ["Original source evidence of driver observation and each statutory position",
                                "Source-backed feasible range and spacing for a physical controller sweep"]}
    write(PROPOSALS / "cases.json", dict(common, sweeps_expanded=True,
                                          sweep_specs=[sweep], cases=cases))
    stage_paths = {"relevance_batch": PROPOSALS / "relevance-batch.json",
                   "relevance": PROPOSALS / "relevance.json",
                   "template": PROPOSALS / "template.json",
                   "judgment_observables": judgment_refs,
                   "bindings": PROPOSALS / "bindings.json",
                   "cases": PROPOSALS / "cases.json"}
    def ref(path):
        return {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
    references = {stage: [ref(path) for path in value] if isinstance(value, list) else ref(value)
                  for stage, value in stage_paths.items()}
    write(PROPOSALS / "semantic-index.json", {"format": "worker-semantic-delivery",
                                               "assignment_id": aid, "stages": references})
    print(json.dumps({"selected_cases": len(manifest["cases"]),
                      "semantic_index_sha256": sha(PROPOSALS / "semantic-index.json")}))


if __name__ == "__main__":
    main()
