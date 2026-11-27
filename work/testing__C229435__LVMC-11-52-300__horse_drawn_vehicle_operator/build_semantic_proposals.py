"""Author draft canonical stage proposals from frozen nighttime parking scope."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAW = "LVMC-11-52-300"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    assignment = json.loads((ROOT.parents[1] / "inputs" / plan["assignment_id"] / "assignment.json").read_text())
    aid, actor, cell = (assignment[key] for key in ("assignment_id", "actor", "cell_id"))
    law_text = assignment["law"]["text"]
    output = ROOT / "proposals"
    relevance = {
        "cell_id": cell, "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": law_text,
                           "applies_to": [actor], "relevance_type": "source-gated nighttime street parking of a nonmotor carriage with another vehicle present",
                           "confidence": "low", "notes": "Carriage classification, parking activity, street and civil-time applicability require independent original sources."}],
        "borderline_excluded": [],
    }
    template_id = LAW + "@" + actor
    parameters = [
        {"name": "parking_duration_s", "kind": "world_setup", "range_or_domain": "1799, 1800 or 1801 measured original seconds"},
        {"name": "civil_start_local", "kind": "world_setup", "range_or_domain": "source-reviewed local date/time across 01:00 and 06:00 endpoints"},
        {"name": "self_propelled_request", "kind": "world_setup", "range_or_domain": "source-reviewed nonmotor versus motor vehicle construction"},
        {"name": "activity_kind", "kind": "controller", "range_or_domain": "actual parking or actual loading activity, independently observed"},
    ]
    template = {
        "template_id": template_id, "law_id": LAW, "actor": actor, "status": "draft", "quote": law_text,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "A responsible person places a qualifying vehicle on a City street during the local 01:00–06:00 interval; original source review remains required.", "numeric_conditions": []},
            "obligation": {"description": "Retain actual nonmotor vehicle parking duration against the strict thirty-minute boundary for independent review.", "type": "must_not",
                           "numeric_conditions": [{"name": "thirty_minute_boundary", "value": 1800, "unit": "s", "operator": "greater_than", "variable": "parking_duration_s"}]},
            "exceptions": [{"source_clause": "Except for a motor vehicle", "description": "Source-proven motor vehicle exception; a horse-drawn actor label does not establish classification."}],
            "timing": {"description": "Measure original civil-time parking episode and overlap with 01:00–06:00; retain exact endpoint interpretation for independent review.", "numeric_conditions": []},
            "judgment_calls_needed": [],
        },
        "parameter_refs": parameters,
    }
    binding = {
        "cell_id": cell, "actor": actor, "status": "draft",
        "established_contexts": ["frozen road/park/other_vehicle cell; original source review required"],
        "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{**item, "used_by_laws": [LAW]} for item in parameters],
    }
    descriptions = []
    for observation in plan["observations"]:
        descriptions.append({"name": observation["name"], "unit": "structured original source record",
                             "sampling_rate_hz": 20,
                             "method": "Original Native 20 Hz source acquisition and saved-only measurement",
                             "time_window": "full synchronized 1805.05-second capture",
                             "reference_frame": "original Native world frame and civil clock mapping",
                             "uncertainty": "Physical classification, activity and pixel visibility require independent source review"})
    recording = {"channels": descriptions,
                 "context_inputs": [{"name": "reviewed_site_and_vehicle_dossiers", "unit": "structured original source record", "method": "Source-hashed OpenDRIVE, municipal, vehicle-build and person-activity dossiers"}],
                 "limitations": ["No original physical or legal acceptance is claimed by a draft proposal."]}
    def assignments(design):
        return {
            "parking_duration_s": {"kind": "world_setup", "value": design["duration_s"]},
            "civil_start_local": {"kind": "world_setup", "value": design["start_local"]},
            "self_propelled_request": {"kind": "world_setup", "value": design["vehicle_class"] == "motor"},
            "activity_kind": {"kind": "controller", "value": design["purpose"]},
        }
    baseline_design = plan["cases"][2]["design"]
    cases = [{"case_id": aid + "__baseline", "target_law_id": None, "target_type": "baseline",
              "status": "draft", "rationale": "Shared sourced City street and two-vehicle context; neutral baseline is not executed.",
              "variable_assignments": assignments(baseline_design),
              "unresolved_judgment_calls": [], "recording_description": recording}]
    for case in plan["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[1]
        design = case["design"]
        primary = ("parking_duration_s" if suffix in ("night_29m59s", "night_30m00s", "night_30m01s")
                   else "self_propelled_request" if suffix == "motor_vehicle_30m01s"
                   else "activity_kind" if suffix == "loading_30m01s" else "civil_start_local")
        probe = {"primary_variable": primary,
                 "comparison_or_standard": "exact frozen law branch and controlled source-bound comparison",
                 "target_value_or_branch": suffix}
        selected = {"case_id": case["case_id"], "target_law_id": LAW, "target_type": "boundary_probe",
                    "status": "draft", "rationale": "Original physical episode and classification must be measured; no legal outcome is requested.",
                    "variable_assignments": assignments(design),
                    "unresolved_judgment_calls": [], "recording_description": recording,
                    "paired_probe_id": "night_parking_full_comparison",
                    "deliberate_differences": list(assignments(design)), "probe": probe}
        if primary == "parking_duration_s":
            probe.update(threshold_ref="obligation.numeric_conditions[0]", operator="greater_than", unit="s", test_value=design["duration_s"])
            selected["epsilon_used"] = {"value": 1, "unit": "s", "rationale": "One-second engineering spacing; no legal tolerance is invented."}
        cases.append(selected)
    proposal = {"cell_id": cell, "actor": actor, "status": "draft", "sweeps_expanded": True,
                "cases": cases, "sweep_specs": []}
    for name, value in (("relevance.json", relevance), ("template.json", template),
                        ("bindings.json", binding), ("cases.json", proposal)):
        write(output / name, value)
    index = {"format": "worker-semantic-delivery", "assignment_id": aid,
             "source": {"path": f"inputs/{aid}/assignment.json", "sha256": sha(ROOT.parents[1] / "inputs" / aid / "assignment.json")},
             "stages": {
                 "relevance_batch": {"path": "proposals/relevance.json", "sha256": sha(output / "relevance.json")},
                 "relevance": {"path": "proposals/relevance.json", "sha256": sha(output / "relevance.json")},
                 "template": {"path": "proposals/template.json", "sha256": sha(output / "template.json")},
                 "judgment_observables": [],
                 "bindings": {"path": "proposals/bindings.json", "sha256": sha(output / "bindings.json")},
                 "cases": {"path": "proposals/cases.json", "sha256": sha(output / "cases.json")},
             }, "status": "draft_local_source_and_physical_review_pending"}
    write(output / "semantic-index.json", index)


if __name__ == "__main__":
    main()
