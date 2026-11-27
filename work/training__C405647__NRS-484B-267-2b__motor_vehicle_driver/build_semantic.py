"""Bind exact NRS 484B.267(2)(b) proposals to five selected CPU cases."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
LAW_ID = LAW["id"]
ACTOR = ASSIGNMENT["actor"]
TEMPLATE_ID = LAW_ID + "@" + ACTOR


def put(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": path.relative_to(HERE).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {"cell_id": "C405647", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW_ID, "quote": LAW["text"],
                                    "applies_to": [ACTOR], "relevance_type": "direct",
                                    "confidence": "high",
                                    "notes": "The emergency-vehicle travel cell can request a passing approach; official role, flashing qualification, visible preparation, officer direction and qualitative caution need original source review."}],
                 "borderline_excluded": []}
    r1 = put("relevance_batch.json", relevance)
    r2 = put("relevance.json", relevance)
    judgments = [
        {"phrase": "authorized emergency vehicle or an official vehicle of a regulatory agency",
         "note": "Blueprint identity alone does not prove authorization or regulatory agency status."},
        {"phrase": "moving or preparing to move in any direction",
         "note": "Original motion or a hand signal visible to the approaching driver is required; 0.05 m/s is only a sensor convention."},
        {"phrase": "making use of flashing lights meeting the requirements of subsection 3 of NRS 484A.480",
         "note": "Original equipment qualification and full-frame pixel review are distinct sources."},
        {"phrase": "Proceed with caution",
         "note": "Speed, surface clearance, time to conflict and braking are diagnostics; no numeric legal caution cutoff is supplied."},
        {"phrase": "except when otherwise directed by a law enforcement officer",
         "note": "Officer identity, direction content, recipient, visibility and time require original review."},
    ]
    parameters = [
        {"name": "requested_response", "kind": "controller",
         "range_or_domain": ["slow_wide", "fast_narrow"]},
        {"name": "requested_source_mode", "kind": "world_setup",
         "range_or_domain": ["moving_vehicle", "visible_hand_signal"]},
        {"name": "requested_role", "kind": "world_setup",
         "range_or_domain": ["authorized_emergency", "official_regulatory"]},
        {"name": "officer_direction_requested", "kind": "world_setup",
         "range_or_domain": [True, False]},
    ]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": ACTOR,
                "quote": LAW["text"], "status": "draft", "structure": {
                    "law_id": LAW_ID,
                    "activation": {"condition": "A qualifying authorized emergency or regulatory official vehicle is moving or visibly preparing to move with qualifying flashing lights as another driver approaches.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Proceed with caution while approaching the qualifying moving or visibly preparing vehicle, unless otherwise directed by a law enforcement officer.",
                                   "type": "must", "numeric_conditions": []},
                    "exceptions": [{"source_clause": "except when otherwise directed by a law enforcement officer",
                                    "description": "Original officer direction may change the required response."}],
                    "timing": {"description": "Review the source-defined approach and response interval; 30 seconds is a recording requirement, not a statutory deadline.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": judgments},
                "parameter_refs": parameters}
    r3 = put("template.json", template)
    observed = []
    channels = ("drv.responding_emergency", "rel.visible",
                "drv.responding_emergency", "kin.speed",
                "dev.human_direction")
    for i, judgment in enumerate(judgments):
        observed.append(put(f"judgment_observables_{i}.json", {
            "template_id": TEMPLATE_ID, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft",
            "observable_requirements": {
                "observables": [{"name": channels[i], "unit": "structured",
                                 "description": "Original Native actor, lane, pixel and source-context join."}],
                "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "dev.human_direction", "unit": "structured",
                                     "description": "Retain synchronized original four-view pixels and actor frames."}],
                "limitations": [judgment["note"],
                                "Synthetic fixture cannot establish physical or legal acceptance."]}}))
    bindings = {"cell_id": "C405647", "actor": ACTOR, "status": "draft",
                "established_contexts": [],
                "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
                "context_refs": [],
                "fixed_parameters": [],
                "variable_parameters": [dict(p, used_by_laws=[LAW_ID]) for p in parameters]}
    r4 = put("bindings.json", bindings)
    recording = json.loads((HERE / "construction.json").read_text())["recording_description"]
    cases = [{"case_id": HERE.name + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Unselected neutral emergency-road context.",
              "variable_assignments": {p["name"]: {"kind": p["kind"], "value": None,
                                                     "unit": "categorical"}
                                       for p in parameters},
              "unresolved_judgment_calls": [],
              "recording_description": recording}]
    configurations = [
        ("slow_wide", "moving_vehicle", "authorized_emergency", False),
        ("fast_narrow", "moving_vehicle", "authorized_emergency", False),
        ("slow_wide", "moving_vehicle", "official_regulatory", False),
        ("slow_wide", "visible_hand_signal", "authorized_emergency", False),
        ("slow_wide", "moving_vehicle", "authorized_emergency", True),
    ]
    for i, values in enumerate(configurations, 1):
        names = [p["name"] for p in parameters]
        assignments = {name: {"kind": p["kind"], "value": value,
                              "unit": "categorical" if isinstance(value, str) else "boolean"}
                       for name, value, p in zip(names, values, parameters)}
        cases.append({"case_id": HERE.name + f"__probe_0{i}",
                      "target_law_id": LAW_ID, "target_type": "judgment_sweep",
                      "rationale": "Exact requested speed/clearance, official-role, visibly preparing or officer-direction alternative; qualification and caution remain for original review.",
                      "variable_assignments": assignments,
                      "unresolved_judgment_calls": [j["phrase"] for j in judgments],
                      "paired_probe_id": HERE.name + "__caution_response",
                      "deliberate_differences": ["requested_response", "requested_source_mode",
                                                "requested_role",
                                                "officer_direction_requested"],
                      "probe": {"primary_variable": "requested_response",
                                "comparison_or_standard": "Four controlled comparisons in case-plan.json; original source activation and qualitative caution review required",
                                "target_value_or_branch": values[0]},
                      "recording_description": recording, "selection_rank": i})
    sweep = {"sweep_id": HERE.name + "__source_judgments",
             "target_law_id": LAW_ID, "status": "incomplete",
             "judgment_refs": judgments,
             "rationale": "Source qualification, visible preparation, qualitative caution and officer direction remain original-review judgments; selected speed/clearance probes do not create legal cutoffs.",
             "missing_inputs": ["Original agency authorization, lamp equipment and pixels, approach, caution and officer-direction review."]}
    r5 = put("cases.json", {"cell_id": "C405647", "actor": ACTOR,
                             "status": "draft", "sweep_specs": [sweep],
                             "sweeps_expanded": True, "cases": cases})
    put("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": HERE.name,
        "stages": {"relevance_batch": r1, "relevance": r2, "template": r3,
                   "judgment_observables": observed, "bindings": r4, "cases": r5}})
    print(json.dumps({"selected_cases": len(cases) - 1, "judgments": len(judgments)}))


if __name__ == "__main__":
    main()
