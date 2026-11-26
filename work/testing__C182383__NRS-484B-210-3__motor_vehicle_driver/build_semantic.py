"""Author exact paved-edge right-side pass cases and draft semantics."""

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
    if plan["assignment_id"] != AID or len(plan["cases"]) != 4 or len(plan["comparisons"]) != 3:
        raise ValueError("four exact paved-edge cases and three comparisons required")
    ids = [item["case_id"] for item in plan["cases"]]
    variation = {"narrow_off_pavement": (False, True, True),
                 "wide_on_pavement": (True, True, False),
                 "wide_off_pavement": (True, True, True),
                 "narrow_no_pass": (False, False, False)}
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        if suffix not in variation:
            raise ValueError("unexpected paved-edge case")
        case["requested_zero_clearance_paved_fit"], case["requested_right_pass"], case["requested_off_pavement"] = variation[suffix]
        case["kind"] = "delivery"
        case["new_capture_selected"] = True
        case["target_law_id"] = LAW
        case["construction_status"] = "source_gated_native_bundle_cpu_preparation"
        case["candidate_risk"] = {"status": "physical", "reason": case["physical_risk"]}
    plan["selected_branch"] = plan["selected_branches"][0]["branch"]
    plan["observations"] = [{"name": channel["name"], "method": channel["method"],
                              "source": "original Native two-actor body capture plus separately classified paved-surface and corridor packet"}
                             for channel in RECORDING["channels"]]
    source = "inputs/" + AID + "/assignment.json"
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "driver overtakes and passes another vehicle upon the right",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "original two-actor longitudinal and lateral body envelopes"},
        {"disposition_index": 1, "requirement": "paved portion of the public highway separately classified",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "source-surveyed pavement classification and edge by road station"},
        {"disposition_index": 2, "requirement": "movement requires driving off paved portion",
         "source": source, "status": "selected_required", "case_ids": ids,
         "evidence_or_gap": "actual off-pavement body extension and zero-clearance lower bound; safe lawful alternative unresolved"}]
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"view": "overview", "subject": "paved edge, ego and overtaken vehicle", "interval": "first through final original frame"},
            {"view": "approach", "subject": "ego entry to right-side pass corridor", "interval": "approach through overlap"},
            {"view": "reference_corner", "subject": "paved/adjacent surface distinction and body envelopes", "interval": "overlap through departure"},
            {"view": "driver_reference", "subject": "actual ego route and overtaken vehicle", "interval": "first through final original frame"}],
        "limitation": "Width alone does not establish a safe lawful paved alternative"}
    plan["planning_status"] = "four_selected_paved_edge_cases_source_gated_cpu_preparation"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    quote = plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [plan["actor"]],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = LAW + "@" + plan["actor"]
    parameters = [
        {"name": "requested_zero_clearance_paved_fit", "kind": "world_setup", "range_or_domain": "narrow or wide surveyed paved corridor", "unit": "source request"},
        {"name": "requested_right_pass", "kind": "world_setup", "range_or_domain": "complete right-side pass or no-pass control", "unit": "source request"},
        {"name": "requested_off_pavement", "kind": "world_setup", "range_or_domain": "actual body path off or on classified pavement", "unit": "source request"}]
    template_ref = put("template.json", {"template_id": template_id, "law_id": LAW,
        "actor": plan["actor"], "status": "draft", "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Driver overtakes and passes another vehicle on the right of a separately classified paved public highway.", "numeric_conditions": []},
            "obligation": {"description": "Do not overtake and pass upon the right when that movement requires driving off the paved portion.", "type": "must_not", "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "Measure original body overlap and paved-edge departure through whole pass; preserve physical-necessity judgment.", "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": parameters})
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Common source-reviewed public highway, classified pavement, two actors and connected corridor; no accepted recording or legal verdict.",
        "variable_assignments": {"requested_zero_clearance_paved_fit": assign(True),
                                 "requested_right_pass": assign(True),
                                 "requested_off_pavement": assign(False)},
        "unresolved_judgment_calls": ["Safe lawful alternative and physical necessity require independent review"],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        fit, passed, off = case["requested_zero_clearance_paved_fit"], case["requested_right_pass"], case["requested_off_pavement"]
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "violating_attempt" if passed and off and not fit else "compliant_attempt",
            "status": "draft", "rationale": "Source-classified paved edge, original body envelopes, actual departure and geometric lower bound are separate; legal necessity unresolved.",
            "paired_probe_id": "right-pass-actual-versus-required-off-pavement",
            "deliberate_differences": ["requested_zero_clearance_paved_fit", "requested_right_pass", "requested_off_pavement"],
            "variable_assignments": {"requested_zero_clearance_paved_fit": assign(fit),
                                     "requested_right_pass": assign(passed),
                                     "requested_off_pavement": assign(off)},
            "unresolved_judgment_calls": ["Safe lawful alternative and physical necessity require independent review"],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "requested_off_pavement" if passed else "requested_right_pass",
                      "comparison_or_standard": "same surveyed road frame, actors, cameras and duration except stated corridor/path change",
                      "target_value_or_branch": str(fit) + "/" + str(passed) + "/" + str(off)}})
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("paved-edge semantic cases:", build())
