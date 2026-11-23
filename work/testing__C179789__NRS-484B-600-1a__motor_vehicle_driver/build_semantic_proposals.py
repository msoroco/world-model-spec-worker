"""Build source-bound draft semantic artifacts for the exact speed comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = ROOT / "inputs" / HERE.name / "assignment.json"
PLAN = HERE / "case-plan.json"
OUT = HERE / "proposals"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path.relative_to(HERE)), "sha256": digest(path)}


def build():
    OUT.mkdir(exist_ok=True)
    assignment = json.loads(ASSIGNMENT.read_text())
    plan = json.loads(PLAN.read_text())
    law = assignment["law"]
    law_id, actor, cell = assignment["law_id"], assignment["actor"], assignment["cell_id"]
    quote = law["text"]
    template_id = law_id + "@" + actor
    note = "Preserve actual speed and contemporaneous traffic, road and weather conditions; legal adequacy remains unresolved."
    judgment = {"phrase": "reasonable or proper", "note": note}
    relevance = {"cell_id": cell, "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law_id, "quote": quote, "applies_to": [actor],
                                    "relevance_type": "basic speed under traffic, highway and weather conditions",
                                    "confidence": "medium",
                                    "notes": "Paved-road travel and another vehicle are assigned; actual conditions and legal adequacy require original evidence."}],
                 "borderline_excluded": []}
    template = {"template_id": template_id, "law_id": law_id, "actor": actor,
                "quote": quote, "status": "draft",
                "structure": {"law_id": law_id,
                              "activation": {"condition": "Person drives or operates a vehicle.", "numeric_conditions": []},
                              "obligation": {"description": "Do not drive at a rate of speed greater than is reasonable or proper, having due regard for the stated conditions.",
                                             "type": "must_not", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Assess speed against contemporaneous traffic, highway and weather conditions.", "numeric_conditions": []},
                              "judgment_calls_needed": [judgment]},
                "parameter_refs": [{"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "observed m/s"},
                                   {"name": "leader_gap", "kind": "world_setup", "range_or_domain": "observed m"},
                                   {"name": "surface_wetness", "kind": "world_setup", "range_or_domain": "observed fraction"},
                                   {"name": "highway_width", "kind": "world_setup", "range_or_domain": "mapped OpenDRIVE cross section in m; statutory boundary unverified"},
                                   {"name": "precipitation_strength", "kind": "world_setup", "range_or_domain": "observed Native scale"},
                                   {"name": "fog_density", "kind": "world_setup", "range_or_domain": "observed Native scale"}]}
    channels = [("ego_speed_mps", "m/s"), ("leader_gap_m", "m"),
                ("highway_width_m", "m"), ("roadway_driving_width_m", "m"),
                ("shoulder_width_m", "m"), ("surface_wetness", "fraction"),
                ("precipitation_strength", "Native scale"), ("fog_density", "Native scale"),
                ("tire_friction", "Native tire friction")]
    observations = [{"name": name, "unit": unit,
                     "description": "Original Native per-frame condition or vehicle observation, with the full history retained."}
                    for name, unit in channels]
    context = [{"name": "authored_speed_conditions", "unit": "reviewed setup",
                "description": "Source-hashed requested values, separate from realized measurements."},
               {"name": "original_road_actor_ids", "unit": "Native source identities",
                "description": "Original road, lane and participant identities."}]
    observable = {"template_id": template_id, **judgment, "status": "draft",
                  "observable_requirements": {"observables": observations,
                                              "context_inputs": context,
                                              "sweep_dimensions": observations[:6],
                                              "landmarks": [],
                                              "recording_needs": observations,
                                              "limitations": ["The mapped OpenDRIVE cross section does not establish statutory boundary-to-boundary highway width.",
                                                              "These physical observations do not define a reasonable or proper speed or a legal verdict."]}}
    names = [("ego_speed", "subject_behavior", "Actual speed is trace-only; never guaranteed."),
             ("commanded_approach_speed", "controller", "Scalar m/s target mapped to ego_speed_request_mps in the Native setup."),
             ("leader_gap", "world_setup", "Leader initial gap in m; maps to leader_initial_gap_m."),
             ("surface_wetness", "world_setup", "Requested wetness fraction; maps to surface_wetness_request."),
             ("highway_width", "world_setup", "Requested mapped OpenDRIVE cross-section width in m; maps to highway_width_m; legal boundary remains unverified."),
             ("precipitation_strength", "world_setup", "Native precipitation request; maps to native_precipitation_request."),
             ("fog_density", "world_setup", "Native fog request; maps to native_fog_request.")]
    binding = {"cell_id": cell, "actor": actor, "status": "draft",
               "established_contexts": ["Assigned paved-road travel with another vehicle; original road authority and realized conditions pending."],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain, "used_by_laws": [law_id]}
                                       for name, kind, domain in names]}
    recording = {"channels": [{"name": name, "unit": unit,
                                "sampling_rate_hz": 20,
                                "method": "Original Native per-frame readback saved in original-conditions.jsonl",
                                "time_window": "All 900 captured frames",
                                "reference_frame": "Original Native world and vehicle state",
                                "uncertainty": "Native sample precision; physical cause remains subject to saved comparison audit"}
                               for name, unit in channels],
                 "context_inputs": [{"name": item["name"], "unit": item["unit"],
                                     "method": item["description"]} for item in context],
                 "limitations": ["OpenDRIVE mapped width is not proof of statutory highway boundaries.",
                                 "Authored requests are not measured outcomes; legal judgment is unresolved."]}
    assignments = {name: {"kind": kind, "value": None} for name, kind, _ in names}
    reference_id = next(c["case_id"] for c in plan["cases"] if c["case_id"].endswith("__reference"))
    baseline = {"case_id": assignment["assignment_id"] + "__shared_baseline",
                "target_law_id": None, "target_type": "baseline",
                "rationale": "Shared paved-road setup identity; numeric source-packet values pending review.",
                "variable_assignments": assignments,
                "unresolved_judgment_calls": [judgment["phrase"]],
                "deliberate_differences": [], "recording_description": recording}
    comparison_by_second = {c["case_ids"][1]: c for c in plan["comparisons"]}
    cases = [baseline]
    for source in plan["cases"]:
        case_id = source["case_id"]
        pair = comparison_by_second.get(case_id)
        variable = ({"ego_speed_request_mps": "commanded_approach_speed",
                     "leader_initial_gap_m": "leader_gap",
                     "surface_wetness_request": "surface_wetness",
                     "highway_width_m": "highway_width",
                     "native_precipitation_request": "precipitation_strength",
                     "native_fog_request": "fog_density"}[pair["deliberate_differences"][0]]
                    if pair else "commanded_approach_speed")
        cases.append({"case_id": case_id, "target_law_id": law_id,
                      "target_type": "judgment_sweep",
                      "rationale": "Exact frozen case identity; requested setup must be source-bound before physical execution.",
                      "paired_probe_id": "c179789-" + (pair["comparison_id"] if pair else "speed"),
                      "comparison_reference_case_id": reference_id if pair else None,
                      "deliberate_differences": [variable] if pair else [],
                      "probe": {"primary_variable": variable,
                                "comparison_or_standard": "frozen physical comparison; statutory judgment unresolved",
                                "target_value_or_branch": pair["comparison_id"] if pair else "reference"},
                      "variable_assignments": assignments,
                      "unresolved_judgment_calls": [judgment["phrase"]],
                      "recording_description": recording})
    case_plan = {"cell_id": cell, "actor": actor, "status": "draft", "sweeps_expanded": True,
                 "sweep_specs": [{"sweep_id": "c179789-reasonable-speed",
                                  "target_law_id": law_id, "status": "incomplete",
                                  "judgment_refs": [judgment],
                                  "rationale": "No statutory numerical cutoff can be inferred from the frozen case labels.",
                                  "missing_inputs": ["Reviewed numerical Native source packet and physical feasibility for a fixed speed/conditions grid."]}],
                 "cases": cases,
                 "frozen_comparisons": [{"comparison_id": c["comparison_id"],
                                         "case_ids": c["case_ids"],
                                         "deliberate_differences": c["deliberate_differences"]}
                                        for c in plan["comparisons"]]}
    stages = {"relevance_batch": write("relevance_batch.json", relevance),
              "relevance": write("relevance.json", relevance),
              "template": write("template.json", template),
              "judgment_observables": [write("judgment-1.json", observable)],
              "bindings": write("bindings.json", binding),
              "cases": write("cases.json", case_plan)}
    index = {"format": "worker-semantic-delivery", "assignment_id": assignment["assignment_id"],
             "source": {"path": str(ASSIGNMENT.relative_to(ROOT)), "sha256": digest(ASSIGNMENT)},
             "case_plan": {"path": str(PLAN.relative_to(HERE)), "sha256": digest(PLAN)},
             "stages": stages, "status": "draft_numeric_source_and_physical_review_pending"}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
