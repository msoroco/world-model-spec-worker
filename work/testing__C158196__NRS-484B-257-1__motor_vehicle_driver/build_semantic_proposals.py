"""Build source-quoted draft stages for the exact nearest-view yield branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
PLAN = json.loads((HERE / "case-plan.json").read_text())
LAW = "NRS-484B-257-1"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
OUT = HERE / "proposals"


def write(name: str, value: dict) -> dict:
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def named(name: str, description: str) -> dict:
    return {"name": name, "unit": "structured record", "description": description}


def build() -> dict:
    OUT.mkdir(exist_ok=True)
    quote = PLAN["law_text"]
    relevance = {"cell_id": "C158196", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                    "applies_to": [ACTOR],
                                    "relevance_type": "direct signed-intersection driver duty",
                                    "confidence": "medium",
                                    "notes": "Yield branch requires original proof that the cataloged signal does not control."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    judgments = [
        ("at the point nearest the intersection where the driver has a view of approaching traffic on the through highway",
         "The exact view-opening point requires original map and raycast observations; no assumed sight-distance cutoff."),
        ("approaching so closely on such through highway as to constitute an immediate hazard",
         "Immediate hazard has no numerical legal threshold in this subsection."),
        ("yield the right-of-way to other vehicles",
         "Right of way requires source-backed entry and approach context across the whole crossing interval."),
    ]
    variables = [
        ("governing_signal", "world_setup", "observed governing traffic-control signal present or absent"),
        ("through_traffic_occupancy", "world_setup", "original through-highway body occupied or clear during crossing"),
        ("ego_response_policy", "controller", "hold or continue as an engineering probe, not legal outcome"),
        ("yield_sign_site", "world_setup", "same surveyed proper yield sign and nearest-view geometry"),
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": quote,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Proper stop or yield sign erected and governs the driver's approach; neither an officer nor a traffic-control signal actually controls traffic.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "At the ordered reference location, stop or yield; after stopping or slowing at a yield sign, yield to through-highway vehicles during the complete crossing interval.",
                                             "type": "must", "numeric_conditions": []},
                              "exceptions": [
                                  {"trigger": "Traffic is controlled by a police officer.",
                                   "effect": "This subsection does not govern that controlled traffic.",
                                   "replacement_obligation": "Other applicable direction requires separate review.",
                                   "source_clause": "Except when traffic is being controlled by a police officer or a traffic-control signal"},
                                  {"trigger": "Traffic is controlled by a traffic-control signal.",
                                   "effect": "This subsection does not govern that controlled traffic.",
                                   "replacement_obligation": "Other signal duties require separate review.",
                                   "source_clause": "Except when traffic is being controlled by a police officer or a traffic-control signal"}],
                              "timing": {"description": "Original approach, first view, slowing or stop, entry and continuous intersection crossing joined by Native frame.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                        for phrase, note in judgments]},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in variables]}
    refs["template"] = write("template.json", template)
    observed = [
        named("original_ego_body_speed", "Original body corners, velocity and front station by Native frame."),
        named("original_through_body", "Original through-highway body and center station by Native frame."),
        named("original_view_rays", "Original raycast from observed ego body to observed through vehicle."),
        named("original_device_control", "Original sign and per-frame governing signal or officer readback."),
        named("camera_frame_map", "Four synchronized original camera frame identities."),
    ]
    contexts = [
        named("site_geometry", "Surveyed connected routes, through-highway status and intersection polygon."),
        named("reference_exclusions", "Surveyed absence of marked stop line and near-side or sidewalk-derived crosswalk."),
        named("governing_device", "Observed proper yield sign and absence or presence of actual controlling signal."),
    ]
    refs["judgment_observables"] = []
    for index, (phrase, note) in enumerate(judgments, 1):
        value = {"template_id": TEMPLATE, "phrase": phrase, "note": note,
                 "status": "draft",
                 "observable_requirements": {"observables": observed,
                    "context_inputs": contexts, "sweep_dimensions": [],
                    "landmarks": [], "recording_needs": observed,
                    "limitations": ["No legal threshold or verdict is supplied by the worker.",
                                    "Original site and realized motion require independent review."]}}
        refs["judgment_observables"].append(write(f"judgment-{index}.json", value))
    refs["bindings"] = write("bindings.json", {
        "cell_id": "C158196", "actor": ACTOR, "status": "draft",
        "established_contexts": ["intersection", "travel"],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind,
                                 "range_or_domain": domain, "used_by_laws": [LAW]}
                                for name, kind, domain in variables]})
    channels = [{"name": item["name"], "unit": item["unit"],
                 "sampling_rate_hz": 20, "method": item["description"],
                 "time_window": "approach through intersection clearance",
                 "reference_frame": "original Native frame and time",
                 "uncertainty": "20 Hz sample and source precision"} for item in observed]
    context_rows = [{"name": item["name"], "unit": item["unit"],
                     "method": item["description"]} for item in contexts]
    description = {"channels": channels, "context_inputs": context_rows,
                   "limitations": ["Physical site, motion and camera visibility remain unverified.",
                                   "Immediate hazard and right of way remain legal judgments."]}
    defaults = {"governing_signal": "absent", "through_traffic_occupancy": "occupied",
                "ego_response_policy": "hold", "yield_sign_site": "original_survey_pending"}

    def case(case_id: str, kind: str) -> dict:
        values = defaults.copy()
        if kind == "nearest_view_continue":
            values["ego_response_policy"] = "continue"
        elif kind == "nearest_view_clear":
            values["ego_response_policy"] = "continue"
            values["through_traffic_occupancy"] = "clear"
        elif kind == "active_signal_exception":
            values["ego_response_policy"] = "continue"
            values["through_traffic_occupancy"] = "clear"
            values["governing_signal"] = "present"
        assignments = {name: {"kind": variable_kind, "value": values[name],
                              "note": "Planned source-gated physical setup; no legal label."}
                       for name, variable_kind, _ in variables}
        baseline = kind == "baseline"
        result = {"case_id": case_id, "target_law_id": None if baseline else LAW,
                  "target_type": "baseline" if baseline else "boundary_probe",
                  "rationale": "Shared surveyed nearest-view reference." if baseline else
                               next(c["recording_description"] for c in PLAN["cases"]
                                    if c["case_id"] == case_id),
                  "variable_assignments": assignments,
                  "recording_description": description,
                  "unresolved_judgment_calls": [phrase for phrase, _ in judgments]}
        if not baseline:
            differences = {"nearest_view_hold": ["ego_response_policy"],
                           "nearest_view_continue": ["ego_response_policy"],
                           "nearest_view_clear": ["through_traffic_occupancy"],
                           "active_signal_exception": ["governing_signal"]}[kind]
            reference = {"nearest_view_hold": "same-site occupied hold reference",
                         "nearest_view_continue": "same-site occupied hold case",
                         "nearest_view_clear": "same-site occupied continuation case",
                         "active_signal_exception": "same-site clear continuation case"}[kind]
            result.update(paired_probe_id="nearest-view-" + kind,
                          deliberate_differences=differences,
                          probe={"primary_variable": differences[0],
                                 "comparison_or_standard": reference,
                                 "target_value_or_branch": kind})
        return result

    selected = [c["case_id"] for c in PLAN["cases"]]
    cases = [case(ASSIGNMENT + "__baseline", "baseline")]
    cases.extend(case(cid, cid.rsplit("__", 1)[1]) for cid in selected)
    sweeps = [{"sweep_id": f"c158196-nearest-view-judgment-{index}",
               "target_law_id": LAW, "judgment_refs": [{"phrase": phrase, "note": note}],
               "status": "incomplete",
               "rationale": "Original C158196 sign, signal, near-side geometry and through-route feasibility are not exported.",
               "missing_inputs": ["Reviewed original Native site and device inventory",
                                  "Feasible source-backed controller and through-traffic sweep ranges"]}
              for index, (phrase, note) in enumerate(judgments, 1)]
    refs["cases"] = write("cases.json", {"cell_id": "C158196", "actor": ACTOR,
                                          "status": "draft", "cases": cases,
                                          "sweep_specs": sweeps, "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": ASSIGNMENT, "stages": refs})
    return {"selected_cases": len(selected), "judgments": len(judgments)}


if __name__ == "__main__":
    print(build())
