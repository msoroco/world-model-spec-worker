"""Draft exact-source railway stage proposals for later local review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = "LVMC-11-16-030"
ACTOR = "motor_vehicle_driver"
TEMPLATE_ID = LAW + "@" + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def ref(path):
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(value):
    a = json.loads((HERE.parents[1] / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    if a["law_id"] != LAW or a["actor"] != ACTOR or a["cell_id"] != "C410753":
        raise ValueError("railway frozen assignment identity differs")
    return a[value]


def main():
    from build_case_proposal import main as build_case_proposal
    build_case_proposal()
    plan = json.loads((HERE / "case-plan.json").read_text())
    law = assignment("law")
    quote = law["text"]
    relevance = {
        "cell_id": "C410753", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{
            "law_id": LAW, "quote": quote, "applies_to": [ACTOR],
            "relevance_type": "direct", "confidence": "medium",
            "notes": "Frozen paved-road railway crossing cell; physical railway and sight sources require local review."}],
        "borderline_excluded": []}
    template = {
        "law_id": LAW, "actor": ACTOR, "template_id": TEMPLATE_ID,
        "quote": quote, "parameter_refs": [
            {"name": "ego_speed", "kind": "subject_behavior",
             "range_or_domain": "original crossing traversal speed in mph"},
            {"name": "commanded_traversal_speed", "kind": "controller",
             "range_or_domain": "engineering 14, 15 or 16 mph target"},
            {"name": "sight_setup", "kind": "world_setup",
             "range_or_domain": "obscured or clear engineering target"},
            {"name": "exception_setup", "kind": "world_setup",
             "range_or_domain": "none, on-duty flagman, visible nonwarning or warning signal"}],
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "Grade-crossing traversal during the last 100-foot obscured approach with 400-foot railway view in both directions", "numeric_conditions": []},
            "obligation": {"type": "prima_facie_speed_limit",
                           "description": "Measure crossing traversal speed against the statutory prima facie 15 mph value only when the sight condition holds.",
                           "numeric_conditions": [{"variable": "ego_speed", "operator": "<=", "value": 15, "unit": "mph"}]},
            "exceptions": [
                {"source_clause": "where a human flagman is on duty", "trigger": "Reviewed on-duty human flagman at crossing time", "effect": "Section does not apply"},
                {"source_clause": "clearly visible electrical or mechanical railway crossing signal device is installed but does not then indicate the immediate approach of a railway train or car", "trigger": "Reviewed installed visible nonwarning crossing signal at traversal", "effect": "Section does not apply"}],
            "timing": {"description": "Approach sight during last 100 feet, speed while traversing, exception state contemporaneous with traversal.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": "clear and unobstructed view", "note": "The exact text supplies distances but no numerical occlusion threshold."}]}}
    judgment = {
        "template_id": TEMPLATE_ID, "phrase": "clear and unobstructed view",
        "note": "The exact text supplies distances but no numerical occlusion threshold.",
        "status": "draft", "observable_requirements": {
            "observables": [{"name": "railway_approach_sight", "unit": "structured frame", "description": "Original crossing and bidirectional 400-foot ray traces throughout last 100-foot approach."}],
            "context_inputs": [{"name": "reviewed_railway_site", "unit": "source packet", "description": "Reviewed railway geometry, jurisdiction and map identity."}],
            "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": "original_native_frame_history", "unit": "structured frame", "description": "Source-hashed route, ray, body and exception readbacks."}],
            "limitations": ["Legal meaning of clear and unobstructed view remains unresolved."]}}
    binding = {
        "cell_id": "C410753", "actor": ACTOR, "status": "draft",
        "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
        "context_refs": [],
        "established_contexts": ["Frozen paved-road railway crossing cell; physical crossing identity requires reviewed original sources."],
        "fixed_parameters": [{"name": "reviewed_railway_site", "value": "source_packet_pending", "rationale": "Hold the same source-reviewed road/rail site across comparisons."}],
        "variable_parameters": [
            {"name": "ego_speed", "kind": "subject_behavior", "range_or_domain": "original traversal speed mph", "used_by_laws": [LAW]},
            {"name": "commanded_traversal_speed", "kind": "controller", "range_or_domain": "14, 15, 16 mph engineering targets", "used_by_laws": [LAW]},
            {"name": "sight_setup", "kind": "world_setup", "range_or_domain": "obscured or clear", "used_by_laws": [LAW]},
            {"name": "exception_setup", "kind": "world_setup", "range_or_domain": "none, flagman or signal", "used_by_laws": [LAW]}]}
    proposal = json.loads((HERE / "proposals" / "cases.json").read_text())
    recording = json.loads((HERE / "cases" / "obscured_14mph" / "construction.json").read_text())["recording_description"]
    baseline = {
        "case_id": ASSIGNMENT + "__shared_baseline", "target_law_id": LAW,
        "target_type": "baseline", "rationale": "Shared source-reviewed crossing and vehicle for selected comparisons.",
        "variable_assignments": {
            "ego_speed": {"kind": "subject_behavior", "value": None, "unit": "mph"},
            "commanded_traversal_speed": {"kind": "controller", "value": 15, "unit": "mph"},
            "sight_setup": {"kind": "world_setup", "value": "obscured", "unit": "category"},
            "exception_setup": {"kind": "world_setup", "value": "none", "unit": "category"}},
        "recording_description": recording,
        "unresolved_judgment_calls": ["clear and unobstructed view"]}
    for case in proposal["cases"]:
        target = case["variable_assignments"]
        speed = target["engineering_target_traversal_mph"]
        sight = target["engineering_sight_setup"]
        exception = target["exception_setup"]
        case["variable_assignments"] = {
            "ego_speed": {"kind": "subject_behavior", "value": None, "unit": "mph"},
            "commanded_traversal_speed": {"kind": "controller", "value": speed, "unit": "mph"},
            "sight_setup": {"kind": "world_setup", "value": sight, "unit": "category"},
            "exception_setup": {"kind": "world_setup", "value": exception, "unit": "category"}}
        case["target_type"] = "boundary_probe" if sight == "obscured" and exception == "none" else "judgment_sweep"
        case["paired_probe_id"] = "railway_speed_sight_exception"
        case["deliberate_differences"] = ["commanded_traversal_speed", "sight_setup", "exception_setup"]
        case["unresolved_judgment_calls"] = ["clear and unobstructed view"]
        case["probe"] = {"primary_variable": "ego_speed" if case["target_type"] == "boundary_probe" else "sight_setup",
                         "comparison_or_standard": "original crossing speed, sight and exception source contrast",
                         "target_value_or_branch": speed if case["target_type"] == "boundary_probe" else sight + "/" + exception}
        if case["target_type"] == "boundary_probe":
            case["epsilon_used"] = 1
            case["probe"].update({"threshold_ref": "obligation.numeric_conditions[0]", "operator": "<=", "unit": "mph", "test_value": speed})
    proposal["cases"] = [baseline] + proposal["cases"]
    proposal["sweeps_expanded"] = True
    proposal["sweep_specs"][0]["judgment_refs"][0]["note"] = judgment["note"]
    paths = {name: HERE / "proposals" / (name + ".json") for name in
             ("relevance_batch", "relevance", "template", "judgment-1", "bindings", "cases")}
    for name, value in (("relevance_batch", relevance), ("relevance", relevance),
                        ("template", template), ("judgment-1", judgment),
                        ("bindings", binding), ("cases", proposal)):
        write(paths[name], value)
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
             "source": "Exact LVMC 11.16.030 text and frozen C410753 cell",
             "status": "draft", "stages": {name: ref(paths[name]) for name in
                ("relevance_batch", "relevance", "template", "bindings", "cases")}}
    index["stages"]["judgment_observables"] = [ref(paths["judgment-1"])]
    write(HERE / "proposals" / "semantic-index.json", index)
    print(json.dumps({"selected_cases": 7, "baseline": 1, "semantic_stages": 6}))


if __name__ == "__main__":
    main()
