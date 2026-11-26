"""Author exact barrier cases, source mapping and canonical draft stages."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, LAW, RECORDING

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / "proposals"


def put(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assign(value):
    return {"kind": "world_setup", "value": value, "unit": "source request"}


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if plan["assignment_id"] != AID or len(plan["cases"]) != 2:
        raise ValueError("two exact barrier cases required")
    ids = [item["case_id"] for item in plan["cases"]]
    for case in plan["cases"]:
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["construction_status"] = "source_gated_native_bundle_cpu_preparation"
    plan["observations"] = [{"name": channel["name"], "method": channel["method"],
                              "source": "original Native barrier capture"}
                             for channel in RECORDING["channels"]]
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "person drives or operates a vehicle",
         "source": "inputs/" + AID + "/assignment.json", "status": "selected_required",
         "case_ids": ids, "evidence_or_gap": "original driver, vehicle and 20 Hz motion identity"},
        {"disposition_index": 1, "requirement": "on any highway in the City",
         "source": "inputs/" + AID + "/assignment.json", "status": "selected_required",
         "case_ids": ids, "evidence_or_gap": "reviewed Native highway and City source status"},
        {"disposition_index": 2, "requirement": "careless or imprudent manner",
         "source": "inputs/" + AID + "/assignment.json", "status": "selected_required",
         "case_ids": ids, "evidence_or_gap": "barrier and surrounding observations; legal judgment unresolved"}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "motor vehicle, barrier and highway",
             "interval": "first through final original frame"},
            {"view": "approach", "subject": "approach motion and barrier edge",
             "interval": "approach through barrier passage"},
            {"view": "reference_corner", "subject": "body clearance and road edges",
             "interval": "barrier encounter"},
            {"view": "driver_reference", "subject": "driver vehicle trajectory and barrier",
             "interval": "first through final original frame"}],
        "limitation": "Camera placement and physical visibility require original review"}
    plan["planning_status"] = "two_selected_barrier_cases_source_gated_cpu_preparation"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    law, actor, quote = plan["law_id"], plan["actor"], plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = law + "@" + actor
    parameters = [{"name": "route_clearance_profile", "kind": "world_setup",
                   "range_or_domain": "wide or near clear connected route beside the same barrier",
                   "unit": "source request"}]
    judgment = {"phrase": "careless or imprudent", "note":
                "Original motion, barrier clearance and surrounding conditions are evidence, not a numeric legal threshold."}
    template_ref = put("template.json", {"template_id": template_id,
        "law_id": law, "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "Person drives or operates a vehicle on a highway in the City.",
                           "numeric_conditions": []},
            "obligation": {"description": "Driving or operation must not be careless or imprudent.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Original vehicle motion through barrier encounter.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [judgment]},
        "parameter_refs": parameters})
    channels = ("ego_body_motion", "barrier_body_clearance", "highway_city_context",
                "route_realization", "camera_frame_identity")
    judgment_ref = put("judgment-careless-or-imprudent.json", {
        "template_id": template_id, "phrase": judgment["phrase"],
        "note": judgment["note"], "status": "draft", "observable_requirements": {
            "observables": [{"name": name,
                             "unit": next(c["unit"] for c in RECORDING["channels"] if c["name"] == name),
                             "description": "Original source-joined " + name.replace("_", " ")}
                            for name in channels],
            "context_inputs": [{"name": "reviewed_native_barrier_site", "unit": "source record",
                                "description": "Source-sealed highway, City status, barrier, road and surroundings"}],
            "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": name,
                                 "unit": next(c["unit"] for c in RECORDING["channels"] if c["name"] == name),
                                 "description": "Original 20 Hz " + name.replace("_", " ")}
                                for name in channels],
            "limitations": ["A human legal reading remains unresolved."]}})
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": actor,
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(parameters[0], used_by_laws=[law])]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Common reviewed highway/barrier context, no accepted recording or legal verdict.",
        "variable_assignments": {"route_clearance_profile": assign("wide")},
        "unresolved_judgment_calls": [judgment["phrase"]],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        profile = case["route_candidate"]
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Compare original body clearance and motion with fixed barrier and highway; no legal cutoff.",
            "paired_probe_id": profile,
            "deliberate_differences": ["route_clearance_profile"] if profile != "wide" else [],
            "variable_assignments": {"route_clearance_profile": assign(profile)},
            "unresolved_judgment_calls": [judgment["phrase"]],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "route_clearance_profile",
                      "comparison_or_standard": "same highway, barrier, ego and speed controller",
                      "target_value_or_branch": profile}})
    sweep = {"sweep_id": "barrier-manner-review", "target_law_id": law,
        "judgment_refs": [judgment], "status": "incomplete",
        "rationale": "No original physical or legal reading defines a bounded careless/imprudent sweep.",
        "missing_inputs": ["Original motion, surroundings and human legal review"]}
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": actor,
        "status": "draft", "sweep_specs": [sweep], "sweeps_expanded": True,
        "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": AID,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [judgment_ref],
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("barrier semantic cases:", build())
