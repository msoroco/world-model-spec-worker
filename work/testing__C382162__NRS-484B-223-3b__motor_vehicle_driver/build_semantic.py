"""Draft exact numeric center-lane statutory stages without legal outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "proposals"
AID = HERE.name
ASSIGNMENT = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
LAW = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
CELL = ASSIGNMENT["cell_id"]
QUOTE = ASSIGNMENT["law"]["text"]
TEMPLATE = LAW + "@" + ACTOR


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
            "relevance_type": "source-gated shared center-turn-lane distance episode",
            "confidence": "medium", "notes": "Original highway, shared-lane design and body occupancy require review."}],
        "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": QUOTE,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Highway has one exclusive center lane for turning by traffic in both directions; vehicle uses it before a left-hand turn from the highway.",
                           "numeric_conditions": []},
            "obligation": {"description": "Do not travel more than 200 feet in the center turn lane before the left-hand turn from the highway.",
                           "type": "must_not", "numeric_conditions": [
                               {"variable": "observed_center_lane_path_ft", "operator": ">", "value": 200, "unit": "ft"}]},
            "exceptions": [],
            "timing": {"description": "Measure original body entry through exit before the original left-turn departure; retain unresolved boundary interpolation.",
                       "numeric_conditions": []},
            "judgment_calls_needed": []},
        "parameter_refs": [
            {"name": "route_relationship", "kind": "world_setup", "range_or_domain": "from or onto highway"},
            {"name": "commanded_center_lane_target_ft", "kind": "controller", "range_or_domain": "engineering target 190, 200 or 210 ft"},
            {"name": "observed_center_lane_path_ft", "kind": "subject_behavior", "range_or_domain": "original-frame observed path length in feet"}]}
    tref = write("template.json", template)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen C382162 intersection left-turn center-lane cell; original reviewed Native highway and lane design remain a local source prerequisite."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}], "context_refs": [],
        "fixed_parameters": [{"name": "shared_center_lane_design", "value": "source_packet_pending",
                              "rationale": "Hold the single bidirectional exclusive center lane and public-highway identity fixed."}],
        "variable_parameters": [
            {"name": "route_relationship", "kind": "world_setup", "range_or_domain": "from or onto highway", "used_by_laws": [LAW]},
            {"name": "commanded_center_lane_target_ft", "kind": "controller", "range_or_domain": "engineering target 190, 200 or 210 ft", "used_by_laws": [LAW]},
            {"name": "observed_center_lane_path_ft", "kind": "subject_behavior", "range_or_domain": "original-frame measured feet", "used_by_laws": [LAW]}]}
    bref = write("bindings.json", binding)
    first = manifest["cases"][0]
    description = json.loads((HERE / first["construction"]).read_text())["recording_description"]
    def assignments(route, target):
        return {"route_relationship": {"kind": "world_setup", "value": route},
                "commanded_center_lane_target_ft": {"kind": "controller", "value": target},
                "observed_center_lane_path_ft": {"kind": "subject_behavior", "value": None}}
    cases = [{"case_id": AID + "__baseline", "target_law_id": LAW,
              "target_type": "baseline", "rationale": "Source-reviewed shared-lane reference with measured original departure.",
              "variable_assignments": assignments("from_highway", 190),
              "recording_description": description, "unresolved_judgment_calls": []}]
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.removeprefix(AID + "__")
        target = {"short_travel": 190, "boundary_travel": 200,
                  "long_travel": 210, "onto_highway_contrast": 210}[kind]
        onto = kind == "onto_highway_contrast"
        cases.append({"case_id": case_id,
            "paired_probe_id": "from_versus_onto_highway" if onto else "below_at_above_200_feet",
            "rationale": "Original-frame measurement and route applicability only; no legal outcome is assigned.",
            "recording_description": description, "target_law_id": LAW,
            "target_type": "boundary_probe", "unresolved_judgment_calls": [],
            "variable_assignments": assignments("onto_highway" if onto else "from_highway", target),
            "deliberate_differences": ["route_relationship"] if onto else ["commanded_center_lane_target_ft"],
            "epsilon_used": {"value": 10, "unit": "ft", "rationale": "Engineering separation for observed boundary probes, not legal tolerance."},
            "probe": {"primary_variable": "route_relationship" if onto else "commanded_center_lane_target_ft",
                      "comparison_or_standard": "Original body path and left-turn departure against exact source text",
                      "target_value_or_branch": "onto_highway" if onto else target,
                      **({} if onto else {"threshold_ref": "obligation.numeric_conditions[0]",
                                            "operator": ">", "unit": "ft", "test_value": target})}})
    cref = write("cases.json", {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                                 "cases": cases, "sweep_specs": [], "sweeps_expanded": True})
    write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": AID,
        "source": "Exact NRS 484B.223(3)(b) text and frozen C382162 cell", "status": "draft",
        "stages": {"relevance_batch": rel_batch, "relevance": rel, "template": tref,
                   "judgment_observables": [], "bindings": bref, "cases": cref}})
    return len(cases) - 1


if __name__ == "__main__":
    print(build())
