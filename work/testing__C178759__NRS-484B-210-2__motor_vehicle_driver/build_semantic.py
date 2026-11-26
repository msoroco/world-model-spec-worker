"""Author exact right-pass cases, source mapping and canonical draft stages."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, CHANNELS, LAW, RECORDING

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
    if plan["assignment_id"] != AID or len(plan["cases"]) != 3:
        raise ValueError("three exact right-pass cases required")
    ids = [item["case_id"] for item in plan["cases"]]
    for case in plan["cases"]:
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["construction_status"] = "source_gated_native_bundle_cpu_preparation"
    plan["observations"] = [{"name": channel["name"], "method": channel["method"],
                              "source": "original Native right-pass capture"}
                             for channel in RECORDING["channels"]]
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "driver of a vehicle overtakes and passes another vehicle upon the right",
         "source": "inputs/" + AID + "/assignment.json", "status": "selected_required",
         "case_ids": ids, "evidence_or_gap": "original driver and two vehicle identities with behind, alongside-right and ahead body phases"},
        {"disposition_index": 1, "requirement": "conditions permitting such movement in safety",
         "source": "inputs/" + AID + "/assignment.json", "status": "selected_required",
         "case_ids": ids, "evidence_or_gap": "original lane, pavement, approach, lateral, conflict and motion histories; legal judgment unresolved"}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "ego and passed vehicle on paved right-pass route",
             "interval": "first through final original frame"},
            {"view": "approach", "subject": "approach gap and target body",
             "interval": "approach through right-side passage"},
            {"view": "reference_corner", "subject": "lateral body clearance and pavement",
             "interval": "alongside passage"},
            {"view": "driver_reference", "subject": "ego trajectory and crossing actor when present",
             "interval": "first through final original frame"}],
        "limitation": "Camera placement and participant visibility require original review"}
    plan["planning_status"] = "three_selected_right_pass_cases_source_gated_cpu_preparation"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    law, actor, quote = plan["law_id"], plan["actor"], plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = law + "@" + actor
    parameters = [{"name": "right_pass_variant", "kind": "world_setup",
                   "range_or_domain": "open_gap, close_gap or cross_traffic on the same paved right-pass route",
                   "unit": "source request"}]
    judgment = {"phrase": "conditions permitting such movement in safety", "note":
                "Original passing motion, pavement and conflict conditions are evidence, not a numeric legal cutoff."}
    template_ref = put("template.json", {"template_id": template_id,
        "law_id": law, "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "Driver overtakes and passes another vehicle upon the right.",
                           "numeric_conditions": []},
            "obligation": {"description": "Right-side passing is permitted only under conditions permitting movement in safety.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Original whole-maneuver right-side pass.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [judgment]},
        "parameter_refs": parameters})
    channels = tuple(name for name, _, _ in CHANNELS)
    judgment_ref = put("judgment-conditions-permitting-safety.json", {
        "template_id": template_id, "phrase": judgment["phrase"],
        "note": judgment["note"], "status": "draft", "observable_requirements": {
            "observables": [{"name": name,
                             "unit": next(c["unit"] for c in RECORDING["channels"] if c["name"] == name),
                             "description": "Original source-joined " + name.replace("_", " ")}
                            for name in channels],
            "context_inputs": [{"name": "reviewed_native_right_pass_site", "unit": "source record",
                                "description": "Source-sealed paved road, lane, actors and surroundings"}],
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
        "rationale": "Common reviewed paved road and vehicle context, no accepted recording or legal verdict.",
        "variable_assignments": {"right_pass_variant": assign("open_gap")},
        "unresolved_judgment_calls": [judgment["phrase"]],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        profile = case["case_id"].removeprefix(AID + "__")
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Compare original right-side passing space and motion with fixed road and actors; no legal cutoff.",
            "paired_probe_id": profile,
            "deliberate_differences": ["right_pass_variant"] if profile != "open_gap" else [],
            "variable_assignments": {"right_pass_variant": assign(profile)},
            "unresolved_judgment_calls": [judgment["phrase"]],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "right_pass_variant",
                      "comparison_or_standard": "same paved road, ego, target, cameras and controller gains",
                      "target_value_or_branch": profile}})
    sweep = {"sweep_id": "right-pass-safety-review", "target_law_id": law,
        "judgment_refs": [judgment], "status": "incomplete",
        "rationale": "No original physical or legal reading defines a bounded safety sweep.",
        "missing_inputs": ["Original whole maneuver and human safety-condition review"]}
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
    print("right-pass semantic cases:", build())
