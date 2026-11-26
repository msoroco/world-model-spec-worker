"""Author exact school-bus speed cases and canonical draft semantics."""

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
    return {"path": str(path.relative_to(HERE)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assign(value, kind="world_setup", unit="source request"):
    return {"kind": kind, "value": value, "unit": unit}


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if plan["assignment_id"] != AID or len(plan["cases"]) != 4 or len(plan["comparisons"]) != 2:
        raise ValueError("four exact school-bus cases and two comparisons required")
    ids = [item["case_id"] for item in plan["cases"]]
    for case in plan["cases"]:
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["target_law_id"] = LAW
        case["construction_status"] = "source_gated_native_bundle_cpu_preparation"
    plan["selected_branch"] = plan["selected_branches"][0]["branch"]
    plan["observations"] = [{"name": channel["name"], "method": channel["method"],
                              "source": "original Native school-bus capture plus sealed trip packet"}
                             for channel in RECORDING["channels"]]
    source = "inputs/" + AID + "/assignment.json"
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "A school bus",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "sealed qualifying definition branch, all exclusions, driver and bus identity"},
        {"disposition_index": 1, "requirement": "shall not exceed a speed of 55 miles per hour",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "original 20 Hz Native bus velocity, source time and below/at/above requested probes"},
        {"disposition_index": 2, "requirement": "when transporting pupils to and from school",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "sealed trip purpose, active interval, pupil presence and separate count"}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "school bus, surveyed route and sidewalk", "interval": "first through final original frame"},
            {"view": "approach", "subject": "bus motion and route ahead", "interval": "speed approach through target interval"},
            {"view": "reference_corner", "subject": "bus body and sidewalk access relationship", "interval": "first through final original frame"},
            {"view": "driver_reference", "subject": "bus viewpoint and route", "interval": "first through final original frame"}],
        "limitation": "Pupil identity, trip purpose and legal classification are document sourced, not inferred from video"}
    plan["planning_status"] = "four_selected_school_bus_speed_cases_source_gated_cpu_preparation"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    quote = plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [plan["actor"]],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = LAW + "@" + plan["actor"]
    parameters = [
        {"name": "target_speed_mph", "kind": "world_setup", "range_or_domain": "54, 55 or 56 mph",
         "unit": "miles/hour request"},
        {"name": "requested_active_transport_phase", "kind": "world_setup",
         "range_or_domain": "source-verified active or inactive pupil-trip speed interval", "unit": "boolean request"}]
    template_ref = put("template.json", {"template_id": template_id, "law_id": LAW,
        "actor": plan["actor"], "status": "draft", "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Source-confirmed school bus transporting pupils to or from school during measured speed interval.",
                           "numeric_conditions": []},
            "obligation": {"description": "School bus shall not exceed 55 miles per hour during that interval.",
                           "type": "must_not",
                           "numeric_conditions": [{"variable": "school bus speed", "operator": ">", "value": 55,
                                                   "unit": "miles/hour"}]},
            "exceptions": [], "timing": {"description": "Only source-confirmed active pupil transportation frames.",
                                         "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": parameters})
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Common source-reviewed bus, route, sidewalk and trip context; no accepted recording or legal verdict.",
        "variable_assignments": {"target_speed_mph": assign(55, unit="miles/hour request"),
                                 "requested_active_transport_phase": assign(True, unit="boolean request")},
        "unresolved_judgment_calls": ["School-bus definition and actual pupil-trip status require independent source review"],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        speed = case["target_speed_mph"]
        active = case["requested_active_transport_phase"]
        probe = {"primary_variable": "target_speed_mph" if active else "requested_active_transport_phase",
                 "comparison_or_standard": "same source-reviewed bus, road, route, sidewalk, cameras and duration",
                 "target_value_or_branch": speed if active else "inactive transport"}
        if active:
            probe.update({"threshold_ref": "obligation.numeric_conditions[0]",
                          "operator": ">", "unit": "miles/hour", "test_value": speed})
        selected_case = {"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Compare original speed and source-confirmed pupil-trip status; commanded target does not decide legal result.",
            "paired_probe_id": "school-bus-55-mph-boundary" if active else "school-bus-transport-phase",
            "deliberate_differences": ["target_speed_mph", "requested_active_transport_phase"],
            "variable_assignments": {"target_speed_mph": assign(speed, unit="miles/hour request"),
                                     "requested_active_transport_phase": assign(active, unit="boolean request")},
            "unresolved_judgment_calls": ["School-bus definition and actual pupil-trip status require independent source review"],
            "recording_description": RECORDING,
            "probe": probe}
        if active:
            selected_case["epsilon_used"] = {"value": 1, "unit": "miles/hour",
                                              "rationale": "One mph controlled construction spacing around exact 55 mph statutory boundary"}
        selected.append(selected_case)
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("school-bus semantic cases:", build())
