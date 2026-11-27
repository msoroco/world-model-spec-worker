"""Author draft NRS 484B.400(1) stage proposals from exact case plan."""

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
    if plan["assignment_id"] != AID or len(plan["cases"]) != 5 or len(plan["comparisons"]) != 4:
        raise ValueError("five exact conditional right-turn cases and four comparisons required")
    plan["selected_branch"] = plan["selected_branches"][0]["branch"]
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "T junction, right-turn lane and connected exit", "interval": "first through final original frame"},
            {"view": "approach", "subject": "driver vehicle and source-selected approach lane", "interval": "approach through junction entry"},
            {"view": "reference_corner", "subject": "source-selected turn lane and vehicle body", "interval": "junction entry through connected exit"},
            {"view": "driver_reference", "subject": "vehicle path, turn and exit", "interval": "first through final original frame"}],
        "limitation": "Video supplements original lane and body readback; it cannot by itself establish lane qualification or legal outcome."}
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    quote = plan["law_text"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [plan["actor"]],
                                    "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = LAW + "@" + plan["actor"]
    parameters = [
        {"name": "qualifying_right_turn_lane", "kind": "world_setup",
         "range_or_domain": "reviewed NRS 484B.223(4) qualification true or false", "unit": "source fact"},
        {"name": "approach_lane_request", "kind": "world_setup",
         "range_or_domain": "source-surveyed right-turn or extreme-right lane", "unit": "source request"},
        {"name": "turn_lane_request", "kind": "world_setup",
         "range_or_domain": "source-surveyed right-turn or extreme-right lane", "unit": "source request"}]
    template_ref = put("template.json", {"template_id": template_id, "law_id": LAW,
        "actor": plan["actor"], "status": "draft", "quote": quote,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Identified driver intends right turn at a public-highway non-alley intersection.",
                           "numeric_conditions": []},
            "obligation": {"description": "Both approach and right turn from the qualified right-turn lane, or the extreme right lane if no such lane exists.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Observe source-joined approach and turn intervals separately; no numeric entry deadline is supplied.",
                       "numeric_conditions": []},
            "judgment_calls_needed": ["NRS 484B.223(4) lane qualification requires independent source review"]},
        "parameter_refs": parameters})
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "status": "draft",
                "rationale": "Common reviewed driver, public highway and T junction; no physical or legal outcome asserted.",
                "variable_assignments": {"qualifying_right_turn_lane": assign(True),
                                         "approach_lane_request": assign("turn"),
                                         "turn_lane_request": assign("turn")},
                "unresolved_judgment_calls": ["Original lane qualification and physical realization remain for review"],
                "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        qualified, approach, turn = (case["qualifying_right_turn_lane"],
                                     case["approach_lane_request"], case["turn_lane_request"])
        selected.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "compliant_attempt" if (approach == turn == ("turn" if qualified else "extreme")) else "violating_attempt",
            "status": "draft", "rationale": "Measure both original lane intervals under independently reviewed conditional lane design; no legal verdict.",
            "paired_probe_id": "conditional-right-turn-lane-position",
            "deliberate_differences": ["qualifying_right_turn_lane", "approach_lane_request", "turn_lane_request"],
            "variable_assignments": {"qualifying_right_turn_lane": assign(qualified),
                                     "approach_lane_request": assign(approach),
                                     "turn_lane_request": assign(turn)},
            "unresolved_judgment_calls": ["Original lane qualification and physical realization remain for review"],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "conditional_lane_and_phase_position",
                      "comparison_or_standard": "source-reviewed T junction, driver, right-turn intention, cameras and duration",
                      "target_value_or_branch": str(qualified) + "/" + approach + "/" + turn}})
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": plan["actor"],
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("exact NRS 484B.400(1) semantic cases:", build())
