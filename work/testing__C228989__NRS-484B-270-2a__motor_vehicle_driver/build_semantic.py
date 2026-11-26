"""Build source-gated semantic proposals for all fourteen exact pass scenes."""

import hashlib
import json
from pathlib import Path

from package_spec import RECORDING


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLAN_PATH = HERE / "case-plan.json"
PROPOSALS = HERE / "proposals"


def put(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(value):
    return {"kind": "world_setup", "value": value, "unit": "source request"}


def build():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    cases = plan["cases"]
    law = plan["law_id"]
    aid = plan["assignment_id"]
    actor = plan["actor"]
    quote = plan["law_text"]
    dispositions = [
        {"requirement": "qualifying same-direction cycle or scooter being overtaken or passed",
         "source": "NRS 484B.270(2)(a) activation",
         "status": "selected_required", "case_ids": [c["case_id"] for c in cases],
         "observation": "original actor/rider identities, headings, lanes and eight-vertex relative pass"},
        {"requirement": "driver of motor vehicle exercises due care",
         "source": "NRS 484B.270(2)(a) due-care clause",
         "status": "selected_required", "case_ids": [c["case_id"] for c in cases],
         "observation": "original relative motion, actor bodies, controls and camera visibility; judgment unresolved"},
        {"requirement": "more than one same-direction lane and immediate-left lane",
         "source": "NRS 484B.270(2)(a) lane condition",
         "status": "selected_required", "case_ids": [c["case_id"] for c in cases],
         "observation": "source-hashed lane direction, count and adjacency, including one-lane contrast"},
        {"requirement": "move to immediate-left lane if available and reasonably safe",
         "source": "NRS 484B.270(2)(a) conditional lane-movement clause",
         "status": "selected_required",
         "case_ids": [c["case_id"] for c in cases if c["same_direction_lane_count_requested"] == 2],
         "observation": "original ego lane, left-lane traffic/restrictions/obstructions and trajectories; legal availability and safety unresolved"},
    ]
    for disposition in dispositions:
        disposition["evidence_or_gap"] = (
            "Original Native map, 20 Hz actor/body trace and four cameras are required at local capture; "
            "synthetic CPU fixture establishes only software behavior.")
    plan["requirement_dispositions"] = dispositions
    plan["source_observation_mapping"] = {}
    names = {"qualifying same-direction pass": "ego_control_body",
             "multiple same-direction lanes and immediate-left lane": "lane_topology",
             "left-lane availability and reasonable safety": "left_lane_traffic",
             "due care": "relative_motion"}
    for observation in plan["observations"]:
        observation["law_observation"] = observation.get("law_observation", observation["name"])
        observation["name"] = names.get(observation["law_observation"], observation["name"])
    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    relevance = {"cell_id": plan["cell_id"], "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
                                    "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = law + "@" + actor
    parameters = [{"name": name, "kind": "world_setup", "range_or_domain": domain,
                   "unit": "source request"} for name, domain in (
                       ("control_kind", "bicycle, electric bicycle or electric scooter"),
                       ("same_direction_lane_count_requested", "one or two surveyed same-direction lanes"),
                       ("left_lane_traffic_requested", "open, occupied or not applicable"),
                       ("ego_maneuver_request", "move left, stay, pass or follow"))]
    template_ref = put("template.json", {"template_id": template_id, "law_id": law,
        "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "Motor-vehicle driver overtakes or passes a qualifying bicycle, electric bicycle or electric scooter proceeding in the same direction.",
                           "numeric_conditions": []},
            "obligation": {"description": "Exercise due care and, when more than one same-direction lane exists, move to the immediate-left lane if available and reasonably safe.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [{"source_clause": "if the lane is available and moving into the lane is reasonably safe",
                            "disposition": "original source review required; no invented threshold"}],
            "timing": {"description": "At original overtaking or passing interval and lane movement.",
                       "numeric_conditions": []},
            "judgment_calls_needed": ["due care", "lane available", "reasonably safe"]},
        "parameter_refs": parameters})
    binding_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": actor,
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(parameter, used_by_laws=[law]) for parameter in parameters]})
    baseline = {"case_id": aid + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Shared source-reviewed road/actor baseline; no original acceptance or legal verdict.",
        "variable_assignments": {name: assignment(value) for name, value in (
            ("control_kind", "bicycle"), ("same_direction_lane_count_requested", 2),
            ("left_lane_traffic_requested", "open"), ("ego_maneuver_request", "move_left"))},
        "unresolved_judgment_calls": ["due care", "lane available", "reasonably safe"],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in cases:
        values = {key: case[key] for key in ("control_kind", "same_direction_lane_count_requested",
                                           "left_lane_traffic_requested", "ego_maneuver_request")}
        selected.append({"case_id": case["case_id"], "target_law_id": law,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Controlled Native source-gated overtaking request; original physical and legal judgments unresolved.",
            "paired_probe_id": case["case_id"].rsplit("__", 1)[-1],
            "deliberate_differences": [name for name, value in values.items()
                                      if value != baseline["variable_assignments"][name]["value"]],
            "variable_assignments": {name: assignment(value) for name, value in values.items()},
            "unresolved_judgment_calls": ["due care", "lane available", "reasonably safe"],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "ego_maneuver_request",
                      "comparison_or_standard": "Compare original body pass, lane topology, traffic and motion; no legal conclusion from requested controls.",
                      "target_value_or_branch": case["case_id"]}})
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": actor,
        "status": "draft", "sweep_specs": [], "sweeps_expanded": True, "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": aid,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": [],
                   "bindings": binding_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(cases)


if __name__ == "__main__":
    print("semantic exact cases:", build())
