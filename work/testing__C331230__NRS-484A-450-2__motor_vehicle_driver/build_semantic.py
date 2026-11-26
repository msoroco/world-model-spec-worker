"""Author exact NRS 484A.450(2) crosswalk semantic stage proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "NRS-484A-450-2"
CELL = "C331230"
ACTOR = "motor_vehicle_driver"
QUOTE = ("Every driver of a vehicle approaching a stop intersection indicated by a stop sign shall stop before entering the crosswalk on the near side of the intersection or, if there is no crosswalk, shall stop at a clearly marked stop line, or if none, then at the point nearest the intersecting highway where the driver has a view of approaching traffic on the intersecting highway before entering the intersection.")
TEMPLATE = LAW + "@" + ACTOR
PHRASE = "view of approaching traffic"
NOTE = "The no-crosswalk fallback's view point requires local geometry and traffic review; it is not exercised by selected crosswalk cases."


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": QUOTE, "applies_to": [ACTOR],
          "relevance_type": "governed stop-sign approach and near-side crosswalk",
          "confidence": "medium",
          "notes": "Actual sign governance, near-side crosswalk geometry and physical cessation require original review."}],
        "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": QUOTE,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Driver of a vehicle approaches a stop intersection indicated by a governing stop sign.",
                           "numeric_conditions": []},
            "obligation": {"description": "Stop before entering the crosswalk on the near side of the intersection when that crosswalk exists.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [
                {"source_clause": "or, if there is no crosswalk, shall stop at a clearly marked stop line",
                 "trigger": "No crosswalk", "effect": "Use marked stop line hierarchy",
                 "replacement_obligation": "Stop at clearly marked stop line"},
                {"source_clause": "or if none, then at the point nearest the intersecting highway where the driver has a view of approaching traffic on the intersecting highway before entering the intersection",
                 "trigger": "No crosswalk or marked stop line", "effect": "Use nearest view point",
                 "replacement_obligation": "Stop at nearest point with view before intersection"}],
            "timing": {"description": "Observe approach, cessation before near-side entry, and later crossing on original frames.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
        "parameter_refs": [{"name": "requested_brake_policy", "kind": "controller",
                             "range_or_domain": "halt or rolling probe"},
                            {"name": "crosswalk_marked", "kind": "world_setup",
                             "range_or_domain": "marked or unmarked near-side crosswalk"}]}
    tref = write("template.json", template)
    judgment = {"template_id": TEMPLATE, "phrase": PHRASE, "note": NOTE,
        "status": "draft", "observable_requirements": {
            "observables": [{"name": "original_front_position", "unit": "structured",
                             "description": "Original vehicle-front position relative to the nearer crosswalk or later fallback."}],
            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": "near_side_crosswalk_boundary", "unit": "structured",
                                  "description": "Reviewed boundary and opposing sidewalk connections."}],
            "limitations": ["No-crosswalk nearest-view fallback is outside the selected near-side crosswalk probes."]}}
    jref = write("judgment-1.json", judgment)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen two-way intersection and stop-sign travel cell; actual site governance pending review."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "reviewed_near_crosswalk_site",
                              "value": "source_packet_pending",
                              "rationale": "Hold intersection, sign and actor identity across linked comparisons."}],
        "variable_parameters": [
            {"name": "requested_brake_policy", "kind": "controller",
             "range_or_domain": "halt or rolling", "used_by_laws": [LAW]},
            {"name": "crosswalk_marked", "kind": "world_setup",
             "range_or_domain": "marked or unmarked", "used_by_laws": [LAW]}]}
    bref = write("bindings.json", binding)
    description = json.loads((HERE / "cases/marked_crosswalk_halt/construction.json").read_text())["recording_description"]
    baseline = {"case_id": AID + "__baseline", "paired_probe_id": "baseline",
        "rationale": "Shared governed marked crosswalk stop-sign approach reference.",
        "recording_description": description, "target_law_id": LAW,
        "target_type": "baseline", "unresolved_judgment_calls": [PHRASE],
        "variable_assignments": {"requested_brake_policy": {"kind": "controller", "value": "halt"},
                                 "crosswalk_marked": {"kind": "world_setup", "value": True}},
        "deliberate_differences": ["requested_brake_policy", "crosswalk_marked"],
        "probe": {"primary_variable": "requested_brake_policy",
                  "comparison_or_standard": "original pre-entry cessation and front trajectory",
                  "target_value_or_branch": "halt"}}
    cases = [baseline]
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        key = case_id.removeprefix(AID + "__")
        marked = key.startswith("marked_")
        policy = "halt" if key.endswith("_halt") else "rolling"
        cases.append({"case_id": case_id,
            "paired_probe_id": "marked_crosswalk_cessation" if marked else "unmarked_crosswalk_cessation",
            "rationale": "Measure original front, speed and crossing under reviewed sign/geometry without a preassigned legal outcome.",
            "recording_description": description, "target_law_id": LAW,
            "target_type": "boundary_probe", "unresolved_judgment_calls": [PHRASE],
            "variable_assignments": {"requested_brake_policy": {"kind": "controller", "value": policy},
                                     "crosswalk_marked": {"kind": "world_setup", "value": marked}},
            "deliberate_differences": ["requested_brake_policy"],
            "probe": {"primary_variable": "requested_brake_policy",
                      "comparison_or_standard": "physical cessation before near-side crosswalk entry",
                      "target_value_or_branch": policy}})
    proposed = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": cases,
        "sweep_specs": [{"sweep_id": "nearest_view_point_not_selected", "target_law_id": LAW,
            "judgment_refs": [{"phrase": PHRASE, "note": NOTE}], "status": "incomplete",
            "rationale": "No-crosswalk fallback is not the assigned near-side crosswalk branch.",
            "missing_inputs": ["Source-backed no-crosswalk/stop-line geometry and approaching-traffic view sweep."]}],
        "sweeps_expanded": True}
    cref = write("cases.json", proposed)
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
        "source": "Exact NRS 484A.450(2) text and C331230 frozen cell",
        "status": "draft", "stages": {"relevance_batch": rel_batch,
            "relevance": rel, "template": tref,
            "judgment_observables": [jref], "bindings": bref, "cases": cref}}
    write("semantic-index.json", index)
    return len(cases)-1


if __name__ == "__main__":
    print(build())
