"""Build exact-law draft semantic stages for fourteen hydrant cases."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / "proposals"
PLAN = json.loads((ROOT / "case-plan.json").read_text())
LAW = "LVMC-11-52-130-A4"
ACTOR = "motor_vehicle_driver"
CELL = "C200568"
QUOTE = PLAN["source_law"]["text"]
PHRASE = "where parallel parking is permitted"
NOTE = "Original parking permission selects the statutory distance; curb paint alone does not."


def write(name, value):
    path = PROPOSALS / (name + ".json")
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
                                    "applies_to": [ACTOR], "relevance_type": "specific_duty",
                                    "confidence": "high",
                                    "notes": "Original premises access, hydrant and parking permission require source review."}],
                 "borderline_excluded": []}
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": QUOTE,
                "structure": {"activation": {"condition":
                    "Motor vehicle stops, stands or parks within a source-measured body distance of a hydrant on public or private premises.",
                    "numeric_conditions": []},
                    "obligation": {"type": "must_not", "description":
                        "Retain fifteen feet where parallel parking is permitted and twenty feet where angle or no parking is permitted; independent permission source selects the branch.",
                        "source_clause": "Within the following distances of any fire hydrant",
                        "numeric_conditions": [
                            {"variable": "parallel_hydrant_body_clearance_ft",
                             "operator": "<", "value": 15, "unit": "ft"},
                            {"variable": "angle_or_no_parking_hydrant_body_clearance_ft",
                             "operator": "<", "value": 20, "unit": "ft"}]},
                    "exceptions": [
                        {"source_clause": "when necessary to avoid conflict with other traffic",
                         "description": "Traffic conflict necessity requires original actor motion and independent causal review."},
                        {"source_clause": "in compliance with law",
                         "description": "An applicable law and the exact reason for parking require independent source review."},
                        {"source_clause": "the directions of a police officer or a traffic control device",
                         "description": "Original lawful direction and applicability require independent source review."}],
                    "timing": {"description": "Measure the entire stopped, standing or parked interval and retain frame uncertainty.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [
                    {"name": "parking_permission", "kind": "world_setup",
                     "range_or_domain": "parallel, angle or no parking from original regulatory survey"},
                    {"name": "requested_clearance_ft", "kind": "controller",
                     "range_or_domain": "authored 14.5 to 22 foot clearance targets; actual body distance measured from source"}]}
    observable = {"template_id": template["template_id"], "phrase": PHRASE,
                  "note": NOTE, "status": "draft",
                  "observable_requirements": {
                      "observables": [{"name": "rel.centre_distance", "unit": "ft",
                                       "description": "Original hydrant-to-vehicle-body clearance with survey uncertainty"},
                                      {"name": "st.parking_space", "unit": "structured",
                                       "description": "Original parking permission and angle source"}],
                      "context_inputs": [{"name": "hydrant_parking_survey", "unit": "structured",
                                          "description": "Original premises, hydrant identity and parking permission survey"}],
                      "sweep_dimensions": [], "landmarks": [],
                      "recording_needs": [{"name": "st.fire_hydrant", "unit": "structured",
                                           "description": "Hydrant identity and position over all 600 frames"},
                                          {"name": "kin.extent", "unit": "structured",
                                           "description": "Vehicle body extent for closest-point measurement"}],
                      "limitations": ["Curb paint and sign absence do not remove the source distance rule.",
                                      "Exception declarations do not prove legal applicability.",
                                      "Original Native parking motion and pixels remain unreviewed."]}}
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": [{"name": "public_access_hydrant_cell",
                                         "source": "frozen catalog C200568"}],
               "law_refs": [{"template_id": template["template_id"],
                              "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [
                   {"name": name, "kind": kind, "range_or_domain": domain,
                    "used_by_laws": [LAW]}
                   for name, kind, domain in (
                       ("parking_permission", "world_setup", "parallel or angle parking"),
                       ("hydrant_parking_clearance", "controller", "19.5 or 22 feet"),
                       ("exception_1_applicability", "world_setup", "declared absent or present"),
                       ("exception_2_applicability", "world_setup", "declared absent or present"),
                       ("exception_3_applicability", "world_setup", "declared absent or present"),
                       ("parallel_hydrant_clearance", "controller", "14.5, 15 or 15.5 feet"),
                       ("angle_or_prohibited_hydrant_clearance", "controller", "19.5, 20 or 20.5 feet"))]}
    cases = json.loads((PROPOSALS / "cases.json").read_text())
    cases["status"] = "draft"
    cases["cases"] = [case for case in cases["cases"]
                      if case["case_id"] != ROOT.name + "__baseline"]
    def assignments(suffix):
        values = {"parking_permission": "parallel_permitted" if suffix.startswith("numeric_1_") else "angle_permitted",
                  "hydrant_parking_clearance": 22 if suffix == "witness_1" else 19.5,
                  "exception_1_applicability": "present" if suffix == "exception_1_2" else "absent",
                  "exception_2_applicability": "present" if suffix == "exception_2_2" else "absent",
                  "exception_3_applicability": "present" if suffix == "exception_3_2" else "absent",
                  "parallel_hydrant_clearance": (14.5, 15, 15.5)[int(suffix[-1])] if suffix.startswith("numeric_1_") else 15,
                  "angle_or_prohibited_hydrant_clearance": (19.5, 20, 20.5)[int(suffix[-1])] if suffix.startswith("numeric_2_") else 20}
        kinds = {row["name"]: row["kind"] for row in binding["variable_parameters"]}
        return {name: {"kind": kinds[name], "value": value,
                       "unit": "feet" if "clearance" in name else "categorical"}
                for name, value in values.items()}
    for case in cases["cases"]:
        suffix = case["case_id"].split("__")[-1]
        case["variable_assignments"] = assignments(suffix)
        if suffix.startswith("numeric_"):
            branch = 0 if suffix.startswith("numeric_1_") else 1
            case["target_type"] = "boundary_probe"
            case["probe"].update({"threshold_ref":
                "obligation.numeric_conditions[" + str(branch) + "]",
                "operator": "<", "unit": "ft",
                "test_value": case["variable_assignments"][
                    "parallel_hydrant_clearance" if branch == 0 else
                    "angle_or_prohibited_hydrant_clearance"]["value"]})
            case["epsilon_used"] = {"value": .5, "unit": "ft",
                "rationale": "Authored diagnostic spacing; not a statutory tolerance."}
        else:
            case["target_type"] = "judgment_sweep"
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": LAW,
                "target_type": "baseline",
                "rationale": "Shared source context for all six hydrant comparisons",
                "variable_assignments": assignments("witness_2"),
                "recording_description": cases["cases"][0]["recording_description"],
                "unresolved_judgment_calls": [PHRASE]}
    cases["cases"] = [baseline] + cases["cases"]
    cases["sweep_specs"] = [{"sweep_id": "c200568-parallel-15-foot",
                             "target_law_id": LAW,
                             "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                             "rationale": "Three explicit numeric cases retain the fifteen-foot source branch.",
                             "status": "incomplete",
                             "missing_inputs": ["Original parking permission and body-distance survey remain unavailable."]},
                            {"sweep_id": "c200568-angle-20-foot",
                             "target_law_id": LAW,
                             "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                             "rationale": "Three explicit numeric cases retain the twenty-foot source branch.",
                             "status": "incomplete",
                             "missing_inputs": ["Original angle permission and body-distance survey remain unavailable."]}]
    cases["sweeps_expanded"] = True
    refs = {"relevance_batch": write("relevance_batch", relevance),
            "relevance": write("relevance", relevance),
            "template": write("template", template),
            "judgment_observables": [write("judgment_observables", observable)],
            "bindings": write("bindings", binding),
            "cases": write("cases", cases)}
    index = {"format": "worker-semantic-delivery", "assignment_id": ROOT.name,
             "stages": refs, "status": "draft", "original_native_observed": False}
    print(write("semantic-index", index))


if __name__ == "__main__":
    main()
