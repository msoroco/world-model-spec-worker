"""Draft canonical rail crossing semantics from the exact supplied clause."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = "NRS-484B-560-7a"
TEMPLATE = LAW + "@motor_vehicle_driver"
QUOTE = ("It is unlawful for the driver of any vehicle: When crossing at grade any track or tracks of a railroad, "
    "to fail to completely cross the track or tracks without stopping due to insufficient: "
    "(1) Space for the vehicle on the opposite side of the railroad crossing; or "
    "(2) Undercarriage clearance of the vehicle. As used in this section, “completely cross” means "
    "to travel across a railroad track or tracks in such a manner that the trailing end of the vehicle "
    "is 15 feet or more past the nearest rail of the railroad track or tracks.")


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {"cell_id": "C202465", "actor": "motor_vehicle_driver",
        "status": "draft", "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": ["motor_vehicle_driver"], "relevance_type": "specific_match",
            "confidence": "medium", "notes": "Frozen at-grade rail cell; original opposite-side space, vehicle undercarriage and nearest-rail geometry require independent review."}],
        "borderline_excluded": []}
    rel = write("relevance.json", relevance)
    rel_batch = write("relevance_batch.json", relevance)
    judgments = [{"phrase": "insufficient space on the opposite side",
                  "note": "independent original opposite-side space and stop-cause source needed"},
                 {"phrase": "insufficient undercarriage clearance",
                  "note": "review vehicle clearance against original rail grade and attributable stop"}]
    template = {"template_id": TEMPLATE, "law_id": LAW,
        "actor": "motor_vehicle_driver", "status": "draft", "quote": QUOTE,
        "structure": {"activation": {"condition": "A vehicle enters an at-grade railroad crossing.",
            "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Completely cross without stopping due to insufficient opposite-side space or undercarriage clearance.",
                "numeric_conditions": [{"variable": "trailing_end_clearance", "operator": ">=",
                    "value": 15, "unit": "feet"}]},
            "exceptions": [],
            "timing": {"description": "From entry until trailing end reaches 15 feet past the reference rail.",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments}, "parameter_refs": []}
    template_ref = write("template.json", template)
    observable_refs = []
    for index, (judgment, name) in enumerate(zip(judgments,
            ("rel.surface_gap", "st.grade"))):
        observable_refs.append(write(f"judgment-{index}.json", {
            "template_id": TEMPLATE, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft",
            "observable_requirements": {"observables": [{"name": name, "unit": "structured",
                "description": "Original Native frame joined to reviewed road and authority source"}],
                "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": name, "unit": "structured",
                    "description": "Source recording needed for independent judgment"}],
                "limitations": ["Synthetic rail geometry cannot establish original stop cause or legal outcome."]}}))
    binding = {"cell_id": "C202465", "actor": "motor_vehicle_driver",
        "status": "draft", "established_contexts": [{"name": "at_grade_rail_crossing",
            "source": "frozen cell; original rail, vehicle and opposite-side source review pending"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "opposite_space", "kind": "world_setup",
            "range_or_domain": "sufficient or insufficient opposite-side space",
            "used_by_laws": [LAW]},
            {"name": "undercarriage_clearance", "kind": "world_setup",
             "range_or_domain": "sufficient or deficient original vehicle and rail grade clearance",
             "used_by_laws": [LAW]},
            {"name": "trailing_end_15_feet", "kind": "world_setup",
             "range_or_domain": "just below or exactly at 15 feet past reference rail",
             "used_by_laws": [LAW]}]}
    binding_ref = write("bindings.json", binding)
    selected = json.loads((HERE / "proposals/cases.json").read_text())
    for case in selected["cases"]:
        if case["target_type"] == "controlled_attempt":
            case["target_type"] = "boundary_probe"
        variables = case["variable_assignments"]
        for name in ("opposite_space", "undercarriage_clearance", "trailing_end_15_feet"):
            variables.setdefault(name, {"kind": "world_setup", "value": "held_fixed"})
        suffix = case["case_id"].rsplit("__", 1)[1]
        boundary_values = {"trailing_just_short": 12.959, "trailing_exact": 15.0,
                           "space_clear": 22.146}
        if suffix in boundary_values:
            case["target_type"] = "boundary_probe"
            case["paired_probe_id"] = "trailing-end-15-foot-boundary"
            case["probe"] = {"primary_variable": "trailing_end_15_feet",
                "comparison_or_standard": "15 feet past reference rail",
                "target_value_or_branch": suffix,
                "threshold_ref": "obligation.numeric_conditions[0]",
                "operator": ">=", "unit": "feet",
                "test_value": boundary_values[suffix]}
            case["epsilon_used"] = {"value": 0.001, "unit": "feet",
                "rationale": "Measurement rounding for a source-shaped diagnostic trajectory; not a legal tolerance."}
    selected["sweep_specs"] = [{"sweep_id": f"c202465-original-review-{i}",
        "target_law_id": LAW, "judgment_refs": [judgment],
        "status": "incomplete", "mode": "one_dimensional", "axes": [],
        "rationale": "Original opposite-side space or undercarriage source is required before freezing this judgment sweep.",
        "missing_inputs": ["Original Native source bytes and independent reviewer identity"]}
        for i, judgment in enumerate(judgments)]
    selected["cases"].insert(0, {"case_id": ASSIGNMENT + "__baseline",
        "target_law_id": LAW, "target_type": "baseline",
        "rationale": "Neutral nonselected rail-crossing comparison anchor",
        "probe": {"primary_variable": "opposite_space",
            "comparison_or_standard": "clear crossing with sufficient opposite-side space",
            "target_value_or_branch": "baseline"},
        "variable_assignments": {"opposite_space": {"kind": "world_setup", "value": "space_clear"},
            "undercarriage_clearance": {"kind": "world_setup", "value": "held_fixed"},
            "trailing_end_15_feet": {"kind": "world_setup", "value": "held_fixed"}},
        "recording_description": selected["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["original opposite-side space and undercarriage source"]})
    cases_ref = write("canonical-cases.json", selected)
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": rel_batch, "relevance": rel,
            "template": template_ref, "judgment_observables": observable_refs,
            "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    print(json.dumps(build()))
