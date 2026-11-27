"""Source-bound draft canonical stage proposals for shoulder lamp cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "proposals"
LAW = "NRS-484D-165-3"
CELL = "C183085"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PHRASE = "as near as practicable to the side of the vehicle which is closest to passing traffic"
NOTE = "Original lamp installation and passing traffic side require independent review."


def write(name, value):
    path = HERE / (name + ".json")
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT.parent.parent / "inputs" / ROOT.name /
                             "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    quote = assignment["law"]["text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote,
                                     "applies_to": [ACTOR],
                                     "relevance_type": "specific_duty",
                                     "confidence": "high",
                                     "notes": "Original shoulder, civil time and optical measurements require review."}],
                 "borderline_excluded": []}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote,
                "structure": {"activation": {"condition":
                    "Vehicle parked or stopped on traveled highway or adjacent shoulder during lighting hours with insufficient ambient reveal at 1,000 feet.",
                    "numeric_conditions": [{"variable": "ambient_reveal_distance_ft",
                                            "operator": "<", "value": 1000, "unit": "ft"}]},
                    "obligation": {"type": "must",
                                   "description": "Display lighted front white or amber and rear red lamps while stopped under the activation conditions; equipment must satisfy 500-foot front and rear visibility and near-traffic-side installation.",
                                   "source_clause": "such vehicle shall display lighted lamps meeting the requirements of subsection 1",
                                   "numeric_conditions": [
                                       {"variable": "front_lamp_visibility_ft", "operator": ">=",
                                        "value": 500, "unit": "ft"},
                                       {"variable": "rear_lamp_visibility_ft", "operator": ">=",
                                        "value": 500, "unit": "ft"}]},
                    "exceptions": [],
                    "timing": {"description": "Continuous display for the full stopped interval during the hours specified in NRS 484D.100.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [
                    {"name": "parked_lamp_display", "kind": "controller",
                     "range_or_domain": "display or omit over all 600 frames"},
                    {"name": "ambient_reveal_distance", "kind": "world_setup",
                     "range_or_domain": "990, 1000 or 1010 feet requested; measured bracket required"},
                    {"name": "front_lamp_visibility", "kind": "world_setup",
                     "range_or_domain": "495, 500 or 505 feet requested equipment probe"},
                    {"name": "rear_lamp_visibility", "kind": "world_setup",
                     "range_or_domain": "495, 500 or 505 feet requested equipment probe"}]}
    observable = {"template_id": TEMPLATE, "phrase": PHRASE, "note": NOTE,
                  "status": "draft", "observable_requirements": {
                      "observables": [{"name": "rel.bearing", "unit": "structured",
                                       "description": "Original passing-traffic side and lamp installation position"},
                                      {"name": "sig.position_lamp", "unit": "structured",
                                       "description": "Full-interval command bits and original pixels"}],
                      "context_inputs": [{"name": "shoulder_lighting_survey", "unit": "structured",
                                          "description": "Original map, clock, passing lane and optical protocol survey"}],
                      "sweep_dimensions": [], "landmarks": [],
                      "recording_needs": [{"name": "env.visibility", "unit": "structured",
                                           "description": "Ambient reveal uncertainty bracket"},
                                          {"name": "st.shoulder", "unit": "structured",
                                           "description": "Mapped adjacent shoulder pose"}],
                      "limitations": ["Command bits do not prove emitted lamp color.",
                                      "Synthetic pixels do not establish calibrated optical distance.",
                                      "Near-side practicality needs independent physical review."]}}
    variables = [("parked_lamp_display", "controller", "display or omit"),
                 ("ambient_reveal_distance", "world_setup", "990, 1000 or 1010 feet"),
                 ("front_lamp_visibility", "world_setup", "495, 500 or 505 feet"),
                 ("rear_lamp_visibility", "world_setup", "495, 500 or 505 feet")]
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": [{"name": "adjacent_paved_shoulder_cell",
                                         "source": "frozen catalog C183085"}],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain,
                                        "used_by_laws": [LAW]}
                                       for name, kind, domain in variables]}
    cases = json.loads((HERE / "cases.json").read_text())
    cases["status"] = "draft"
    cases["cases"] = [case for case in cases["cases"]
                      if case["target_type"] != "baseline"]
    comparisons = {case_id: comparison for comparison in plan["comparisons"]
                   for case_id in comparison["case_ids"]}
    def assignments(case):
        suffix = case["case_id"].split("__")[-1]
        values = {"parked_lamp_display": "omit" if suffix == "witness_2" else "display",
                  "ambient_reveal_distance": 1000,
                  "front_lamp_visibility": 500,
                  "rear_lamp_visibility": 500}
        if suffix.startswith("numeric_"):
            _, number, index = suffix.split("_")
            name = {"1": "ambient_reveal_distance", "2": "front_lamp_visibility",
                    "3": "rear_lamp_visibility"}[number]
            values[name] = (990, 1000, 1010)[int(index)] if number == "1" else \
                (495, 500, 505)[int(index)]
        kinds = {name: kind for name, kind, _ in variables}
        return {name: {"kind": kinds[name], "value": value,
                       "unit": "categorical" if name == "parked_lamp_display" else "feet"}
                for name, value in values.items()}
    for case in cases["cases"]:
        suffix = case["case_id"].split("__")[-1]
        case["variable_assignments"] = assignments(case)
        comparison = comparisons[case["case_id"]]
        case["paired_probe_id"] = comparison["comparison_id"]
        case["deliberate_differences"] = comparison["deliberate_differences"]
        if suffix.startswith("numeric_"):
            number = int(suffix.split("_")[1])
            name = ("ambient_reveal_distance", "front_lamp_visibility",
                    "rear_lamp_visibility")[number - 1]
            case["target_type"] = "boundary_probe"
            case["probe"] = {"threshold_ref":
                ("activation.numeric_conditions[0]" if number == 1 else
                 "obligation.numeric_conditions[" + str(number - 2) + "]"),
                "operator": "<" if number == 1 else ">=", "unit": "ft",
                "test_value": case["variable_assignments"][name]["value"],
                "primary_variable": name,
                "comparison_or_standard": "Source-measured statutory optical distance",
                "target_value_or_branch": case["variable_assignments"][name]["value"]}
            case["epsilon_used"] = {"value": 10 if number == 1 else 5,
                "unit": "ft", "rationale": "Authored probe spacing, not a legal tolerance."}
        else:
            case["target_type"] = "judgment_sweep"
            case["unresolved_judgment_calls"] = [PHRASE]
            case["probe"] = {"primary_variable": "parked_lamp_display",
                             "comparison_or_standard": "Continuous lamp display under source-verified low light",
                             "target_value_or_branch": case["variable_assignments"][
                                 "parked_lamp_display"]["value"]}
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": LAW,
                "target_type": "baseline", "rationale": "Shared shoulder source context",
                "variable_assignments": assignments(cases["cases"][0]),
                "recording_description": cases["cases"][0]["recording_description"],
                "unresolved_judgment_calls": [PHRASE]}
    cases["cases"] = [baseline] + cases["cases"]
    cases["sweeps_expanded"] = True
    cases["sweep_specs"] = [{"sweep_id": "c183085-optical-sweep-" + str(i),
                             "target_law_id": LAW,
                             "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                             "rationale": "Three source-measured numeric probe cases.",
                             "status": "incomplete",
                             "missing_inputs": ["Original optical calibration and pixels pending."]}
                            for i in range(1, 4)]
    refs = {"relevance_batch": write("relevance_batch", relevance),
            "relevance": write("relevance", relevance),
            "template": write("template", template),
            "judgment_observables": [write("judgment_observables", observable)],
            "bindings": write("bindings", binding),
            "cases": write("cases", cases)}
    print(write("semantic-index", {"format": "worker-semantic-delivery",
                                   "assignment_id": ROOT.name, "stages": refs,
                                   "status": "draft", "original_native_observed": False}))


if __name__ == "__main__":
    main()
