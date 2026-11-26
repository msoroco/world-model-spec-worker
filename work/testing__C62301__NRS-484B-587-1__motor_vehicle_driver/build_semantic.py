"""Author exact controlled-access entry and exit cases and draft semantics."""

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
    if plan["assignment_id"] != AID or len(plan["cases"]) != 5 or len(plan["comparisons"]) != 3:
        raise ValueError("five exact access cases and three comparisons required")
    ids = [item["case_id"] for item in plan["cases"]]
    variation = {"indicated_entry": ("entry", True, True),
                 "unindicated_entry": ("entry", False, True),
                 "notice_not_visible": ("entry", True, False),
                 "indicated_exit": ("exit", True, True),
                 "unindicated_exit": ("exit", False, True)}
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        if suffix not in variation:
            raise ValueError("unexpected exact access case")
        case["requested_direction"], case["requested_indicated"], case["requested_notice_visible"] = variation[suffix]
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["target_law_id"] = LAW
        case["construction_status"] = "source_gated_native_bundle_cpu_preparation"
    plan["selected_branch"] = plan["selected_branches"][0]["branch"]
    plan["observations"] = [{"name": channel["name"], "method": channel["method"],
                              "source": "original Native access-route capture plus separately sealed authority and official device packet"}
                             for channel in RECORDING["channels"]]
    source = "inputs/" + AID + "/assignment.json"
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "public-authority controlled-access highway determination and public highway boundary",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "independent authority determination and surveyed public highway extent"},
        {"disposition_index": 1, "requirement": "official traffic-control devices erected giving notice of indicated entrances and exits",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "source-sealed official device authority, erection, indication and driver-view visibility"},
        {"disposition_index": 2, "requirement": "person driving a vehicle onto or from highway at indicated entrance or exit",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "original Native vehicle identity, boundary crossing direction and coordinate"}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "public highway boundary, official device and vehicle", "interval": "first through final original frame"},
            {"view": "approach", "subject": "vehicle approach to entry or exit boundary", "interval": "approach through crossing"},
            {"view": "reference_corner", "subject": "erected official device placement and content", "interval": "approach through crossing"},
            {"view": "driver_reference", "subject": "driver-view notice visibility and route", "interval": "first through final original frame"}],
        "limitation": "Original pixels cannot establish legal designation without public-authority source"}
    plan["planning_status"] = "five_selected_access_cases_source_gated_cpu_preparation"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    quote = plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [plan["actor"]],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = LAW + "@" + plan["actor"]
    parameters = [
        {"name": "requested_direction", "kind": "world_setup", "range_or_domain": "entry or exit", "unit": "source request"},
        {"name": "requested_indicated", "kind": "world_setup", "range_or_domain": "officially indicated or unindicated crossing", "unit": "source request"},
        {"name": "requested_notice_visible", "kind": "world_setup", "range_or_domain": "erected notice visible or occluded", "unit": "source request"}]
    template_ref = put("template.json", {"template_id": template_id, "law_id": LAW,
        "actor": plan["actor"], "status": "draft", "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Official traffic-control devices erected giving notice of indicated access points for a separately established controlled-access highway.", "numeric_conditions": []},
            "obligation": {"description": "A person shall not drive a vehicle onto or from the highway except at indicated entrances and exits.", "type": "must_not", "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "Assess official notice and exact entry or exit boundary crossing in original route frames.", "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": parameters})
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Common separately sourced public authority, controlled-access highway, official device inventory and vehicle; no accepted recording or legal verdict.",
        "variable_assignments": {"requested_direction": assign("entry"),
                                 "requested_indicated": assign(True),
                                 "requested_notice_visible": assign(True)},
        "unresolved_judgment_calls": ["Public authority and official device legal status require source review"],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        direction, indicated, visible = case["requested_direction"], case["requested_indicated"], case["requested_notice_visible"]
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "compliant_attempt" if indicated and visible else "violating_attempt",
            "status": "draft", "rationale": "Separate authority and official device sources, original boundary crossing, notice visibility and vehicle identity; no legal verdict.",
            "paired_probe_id": "controlled-access-designation-and-notice",
            "deliberate_differences": ["requested_direction", "requested_indicated", "requested_notice_visible"],
            "variable_assignments": {"requested_direction": assign(direction),
                                     "requested_indicated": assign(indicated),
                                     "requested_notice_visible": assign(visible)},
            "unresolved_judgment_calls": ["Public authority and official device legal status require source review"],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "requested_notice_visible" if not visible else "requested_indicated",
                      "comparison_or_standard": "same authority, highway boundary, official device inventory, vehicle, cameras and duration",
                      "target_value_or_branch": direction + "/" + str(indicated) + "/" + str(visible)}})
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("controlled-access semantic cases:", build())
