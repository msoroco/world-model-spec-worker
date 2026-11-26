"""Write source-grounded canonical draft stages for the blind-intersection speed cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = "LVMC-11-16-040"
ACTOR = "motor_vehicle_driver"
TEXT = json.loads((ROOT.parents[1] / "inputs" / AID / "assignment.json").read_text())["law"]["text"]
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = ROOT / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def channel(name, unit):
    return {"name": name, "unit": unit, "sampling_rate_hz": 20,
            "method": "original Native frame and saved source review",
            "time_window": "full 30-second attempt", "reference_frame": "Native frame",
            "uncertainty": "subject to independent physical and source review"}


def main():
    desc = {"channels": [channel(name, unit) for name, unit in (
        ("ego_speed", "m/s"), ("ego_pose", "structured"),
        ("distance_to_boundary", "m"), ("intersection_sight", "structured"),
        ("entering_approach_visibility", "structured"),
        ("intersection_traversal", "categorical"))],
        "context_inputs": [{"name": "through_street_context", "unit": "structured",
                            "method": "original OpenDRIVE and independent roadway review"},
                           {"name": "traffic_control_context", "unit": "structured",
                            "method": "original Native signal/sign inventory and independent review"}],
        "limitations": ["No legal status follows from a requested speed or CPU fixture.",
                        "Original sight, roadway priority and control facts require review."]}
    (ROOT / "native" / "recording-description.json").write_text(json.dumps(desc, indent=2) + "\n")
    relevance = {"cell_id": "C24758", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": TEXT, "applies_to": [ACTOR],
                    "relevance_type": "specific_match", "confidence": "high",
                    "notes": "The frozen blind-intersection travel cell matches the law; source review determines activation."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance-batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    judgments = [
        {"phrase": "prima facie", "note": "Rebuttable legal status remains for independent review."},
        {"phrase": "clear and unobstructed view", "note": "Review original intersection and all entering-road sight sources."},
        {"phrase": "through street or highway", "note": "Review original roadway priority and applicability."},
        {"phrase": "traffic-controlled intersection", "note": "Review original controls and applicability."}]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "status": "draft", "quote": TEXT,
        "structure": {"activation": {"condition": "Sight-limited intersection traversal after the last 100 feet of approach.",
                                      "numeric_conditions": []},
            "obligation": {"description": "Measure traversal speed against the 15 mph prima facie reference; reserve legal status.",
                           "type": "must", "source_clause": "The prima facie speed limit shall be fifteen miles per hour",
                           "numeric_conditions": [{"variable": "ego_speed", "operator": "<=", "value": 15, "unit": "mph"}]},
            "exceptions": [{"source_clause": "except on a through street or highway",
                            "trigger": "Source-reviewed through street or highway applies.",
                            "effect": "This section's 15 mph reference does not apply.",
                            "replacement_obligation": "Review the applicable original speed authority separately."},
                           {"source_clause": "or at a traffic-controlled intersection",
                            "trigger": "Source-reviewed traffic-controlled intersection applies.",
                            "effect": "This section's 15 mph reference does not apply.",
                            "replacement_obligation": "Review the applicable original speed authority separately."}],
            "timing": {"description": "Retain every sampled frame across the last 100 feet and intersection traversal.",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments},
        "parameter_refs": [{"name": "ego_speed", "kind": "subject_behavior",
                            "range_or_domain": "original Native speed in mph"},
                           {"name": "commanded_approach_speed", "kind": "controller",
                            "range_or_domain": "requested m/s, distinct from observation"},
                           {"name": "through_street_context", "kind": "world_setup",
                            "range_or_domain": "independently reviewed roadway priority"},
                           {"name": "traffic_control_context", "kind": "world_setup",
                            "range_or_domain": "independently reviewed applicable controls"}]}
    refs["template"] = write("template.json", template)
    observed = []
    needs = [[("ego_speed", "m/s"), ("intersection_traversal", "categorical")],
             [("intersection_sight", "structured"), ("entering_approach_visibility", "structured"),
              ("distance_to_boundary", "m")],
             [("through_street_context", "structured")],
             [("traffic_control_context", "structured")]]
    for i, (judgment, items) in enumerate(zip(judgments, needs), 1):
        requirements = [{"name": name, "unit": unit,
                         "description": "Retain original source and Native frame join for " + name}
                        for name, unit in items]
        req = {"observables": requirements, "context_inputs": [],
               "sweep_dimensions": [], "landmarks": [],
               "recording_needs": requirements,
               "limitations": ["Original facts and legal interpretation remain subject to independent review."]}
        observed.append(write("judgment-%d.json" % i,
            {"template_id": TEMPLATE, "phrase": judgment["phrase"],
             "note": judgment["note"], "status": "draft",
             "observable_requirements": req}))
    refs["judgment_observables"] = observed
    binding = {"cell_id": "C24758", "actor": ACTOR, "status": "draft",
        "established_contexts": [], "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "cell_layout", "value": "blind_intersection",
                              "rationale": "Frozen catalog cell."}],
        "variable_parameters": [{"name": item["name"], "kind": item["kind"],
                                 "range_or_domain": item["range_or_domain"], "used_by_laws": [LAW]}
                                for item in template["parameter_refs"]]}
    refs["bindings"] = write("bindings.json", binding)
    def assignments(target):
        return {"ego_speed": {"kind": "subject_behavior", "value": None},
                "commanded_approach_speed": {"kind": "controller", "value": target},
                "through_street_context": {"kind": "world_setup", "value": "reviewed_false"},
                "traffic_control_context": {"kind": "world_setup", "value": "reviewed_false"}}
    cases = [{"case_id": AID + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Common blind-intersection setup before a speed request.",
        "variable_assignments": assignments(None),
        "unresolved_judgment_calls": [j["phrase"] for j in judgments],
        "recording_description": desc}]
    for suffix, target, test_mph in (("reference", 6.2, 13.869),
                                     ("at_15", 6.7056, 15),
                                     ("contrast", 7.2, 16.106)):
        cases.append({"case_id": AID + "__" + suffix, "target_law_id": LAW,
            "target_type": "boundary_probe", "rationale": "Record actual speed and sight evidence; no legal label.",
            "paired_probe_id": "blind_intersection_15_mph",
            "deliberate_differences": ["commanded_approach_speed"],
            "variable_assignments": assignments(target),
            "unresolved_judgment_calls": [j["phrase"] for j in judgments],
            "recording_description": desc,
            "probe": {"primary_variable": "ego_speed", "comparison_or_standard": "15 mph prima facie reference",
                      "target_value_or_branch": suffix, "threshold_ref": "obligation.numeric_conditions[0]",
                      "operator": "<=", "unit": "mph", "test_value": test_mph},
            "epsilon_used": {"value": 1.1, "unit": "mph",
                             "rationale": "Requested separation for physical observation, never legal tolerance."}})
    specs = [{"sweep_id": "sight-and-exception-review-" + str(i),
              "target_law_id": LAW, "judgment_refs": [judgment],
              "status": "incomplete", "rationale": "Preserve source for later physical and legal review.",
              "missing_inputs": ["Original Native capture and independent reviewer evidence."]}
             for i, judgment in enumerate(judgments, 1)]
    refs["cases"] = write("cases.json", {"cell_id": "C24758", "actor": ACTOR,
        "status": "draft", "sweep_specs": specs, "sweeps_expanded": True, "cases": cases})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": AID, "stages": refs})


if __name__ == "__main__":
    main()
