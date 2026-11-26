"""Author exact right-turn-only lane purpose cases and draft semantics."""

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


def assign(value):
    return {"kind": "world_setup", "value": value, "unit": "source request"}


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if plan["assignment_id"] != AID or len(plan["cases"]) != 4 or len(plan["comparisons"]) != 2:
        raise ValueError("four exact T-junction cases and two comparisons required")
    ids = [item["case_id"] for item in plan["cases"]]
    variation = {"right_turn_purpose": ("right_turn", "right_turn"),
                 "through_purpose": ("through", "right_turn"),
                 "left_turn_purpose": ("left_turn", "right_turn"),
                 "right_turn_route_mismatch": ("right_turn", "other")}
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        if suffix not in variation:
            raise ValueError("unexpected exact case")
        case["declared_maneuver_purpose"], case["requested_departure_route"] = variation[suffix]
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["target_law_id"] = LAW
        case["construction_status"] = "source_gated_native_bundle_cpu_preparation"
    plan["selected_branch"] = plan["selected_branches"][0]["branch"]
    plan["observations"] = [{"name": channel["name"], "method": channel["method"],
                              "source": "original Native T-junction capture plus sealed purpose packet"}
                             for channel in RECORDING["channels"]]
    source = "inputs/" + AID + "/assignment.json"
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "public highway designed to provide a single right lane to be used only for turning",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "source-sealed public-highway and exclusive right-turn lane design"},
        {"disposition_index": 1, "requirement": "vehicle driven in the right turn lane",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "original Native lane ID and route position over continuous lane-use interval"},
        {"disposition_index": 2, "requirement": "only for the purpose of making a right turn",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "independent purpose declaration before lane entry, retained beside observed exit"}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "T junction, exclusive right-turn lane and vehicle", "interval": "first through final original frame"},
            {"view": "approach", "subject": "lane entry and turn-only design", "interval": "approach through lane use"},
            {"view": "reference_corner", "subject": "right exit connection and road markings", "interval": "lane use through departure"},
            {"view": "driver_reference", "subject": "vehicle path and right-turn departure", "interval": "first through final original frame"}],
        "limitation": "Purpose must be independently sourced before lane entry; video does not infer purpose"}
    plan["planning_status"] = "four_selected_right_turn_purpose_cases_source_gated_cpu_preparation"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    quote = plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [plan["actor"]],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = LAW + "@" + plan["actor"]
    parameters = [
        {"name": "declared_maneuver_purpose", "kind": "world_setup",
         "range_or_domain": "source-declared right turn, through or left turn before lane entry", "unit": "source request"},
        {"name": "requested_departure_route", "kind": "world_setup",
         "range_or_domain": "connected right exit or independently sourced alternate exit", "unit": "source request"}]
    template_ref = put("template.json", {"template_id": template_id, "law_id": LAW,
        "actor": plan["actor"], "status": "draft", "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Public highway with one exclusive right-turn lane; vehicle is driven within that lane.",
                           "numeric_conditions": []},
            "obligation": {"description": "Vehicle must be driven in that right-turn lane only for the purpose of making a right turn.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "Purpose is sourced before entry and evaluated over original lane-use interval; turn completion is a separate fact.",
                                         "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": parameters})
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Common source-reviewed public highway, lane, T junction and vehicle; no accepted recording or legal verdict.",
        "variable_assignments": {"declared_maneuver_purpose": assign("right_turn"),
                                 "requested_departure_route": assign("right_turn")},
        "unresolved_judgment_calls": ["Purpose sufficiency requires independent source review"],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        purpose, route = case["declared_maneuver_purpose"], case["requested_departure_route"]
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "compliant_attempt" if purpose == route == "right_turn" else "violating_attempt",
            "status": "draft", "rationale": "Separate independently sourced pre-entry purpose, original lane use and observed connected exit; no legal verdict.",
            "paired_probe_id": "right-turn-purpose-and-route",
            "deliberate_differences": ["declared_maneuver_purpose", "requested_departure_route"],
            "variable_assignments": {"declared_maneuver_purpose": assign(purpose),
                                     "requested_departure_route": assign(route)},
            "unresolved_judgment_calls": ["Purpose sufficiency requires independent source review"],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "requested_departure_route" if purpose == "right_turn" and route != "right_turn" else "declared_maneuver_purpose",
                      "comparison_or_standard": "same public highway, exclusive lane, T junction, vehicle, cameras and duration",
                      "target_value_or_branch": purpose + "/" + route}})
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("right-turn-lane semantic cases:", build())
