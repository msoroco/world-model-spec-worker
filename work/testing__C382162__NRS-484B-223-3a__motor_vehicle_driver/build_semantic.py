"""Draft exact statutory relevance, template, judgment, binding and case stages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "NRS-484B-223-3a"
ACTOR = "motor_vehicle_driver"
CELL = "C382162"
QUOTE = ("If a highway has been designed to provide a single center lane to be used only "
         "for turning by traffic moving in both directions, the following rules apply: "
         "A vehicle may be driven in the center turn lane only for the purpose of making "
         "a left-hand turn onto or from the highway.")
TEMPLATE = LAW + "@" + ACTOR
PHRASE = "only for the purpose of making a left-hand turn onto or from the highway"
NOTE = ("Independent pre-entry purpose and observed route are retained separately; "
        "sufficiency is for local review, with no invented distance or duration cutoff.")


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
            "relevance_type": "source-gated shared center-turn-lane purpose episode",
            "confidence": "medium",
            "notes": "Highway designation, both-direction exclusive design and actual occupancy require original source review."}],
        "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": QUOTE,
        "structure": {"law_id": LAW,
            "activation": {"condition": "Highway designed with one center turn-only lane for both traffic directions; qualifying vehicle driven there.",
                           "numeric_conditions": []},
            "obligation": {"description": "Center-lane driving only for a left-hand turn onto or from the highway.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Preserve independently declared purpose before entry and original occupancy/turn history before, during and after lane use.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
        "parameter_refs": [
            {"name": "route_relationship", "kind": "world_setup",
             "range_or_domain": "onto highway or from highway"},
            {"name": "declared_purpose", "kind": "controller",
             "range_or_domain": "left turn onto/from, through travel or right turn"},
            {"name": "junction_kind", "kind": "world_setup",
             "range_or_domain": "street intersection or alley junction"}]}
    tref = write("template.json", template)
    judgment = {"template_id": TEMPLATE, "phrase": PHRASE, "note": NOTE,
        "status": "draft", "observable_requirements": {
            "observables": [
                {"name": "pre_entry_purpose", "unit": "structured",
                 "description": "Independent route/purpose record sealed before actual center-lane entry."},
                {"name": "original_lane_occupancy", "unit": "structured",
                 "description": "Actual original-frame center-lane occupancy and road/turn trajectory."}],
            "context_inputs": [{"name": "reviewed_center_lane_site", "unit": "source",
                                "description": "Single exclusive bidirectional shared center lane on highway."}],
            "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": "original_route_and_maneuver", "unit": "structured",
                                  "description": "Original Native pre/during/post lane route history."}],
            "limitations": ["Purpose sufficiency is not inferred from distance, duration or completed turn."]}}
    jref = write("judgment-1.json", judgment)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen intersection left-turn center-lane cell; reviewed Native highway/lane site required."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "shared_center_lane_design", "value": "source_packet_pending",
                              "rationale": "Hold highway and exclusive bidirectional center-lane design fixed."}],
        "variable_parameters": [
            {"name": "route_relationship", "kind": "world_setup", "range_or_domain": "onto/from highway", "used_by_laws": [LAW]},
            {"name": "declared_purpose", "kind": "controller", "range_or_domain": "left/through/right", "used_by_laws": [LAW]},
            {"name": "junction_kind", "kind": "world_setup", "range_or_domain": "street/alley", "used_by_laws": [LAW]}]}
    bref = write("bindings.json", binding)
    first = manifest["cases"][0]
    description = json.loads((HERE / first["construction"]).read_text())["recording_description"]
    baseline = {"case_id": AID + "__baseline", "paired_probe_id": "baseline",
        "rationale": "Reviewed shared center-lane and left turn from highway reference.",
        "recording_description": description, "target_law_id": LAW,
        "target_type": "baseline", "unresolved_judgment_calls": [PHRASE],
        "variable_assignments": {
            "route_relationship": {"kind": "world_setup", "value": "from_highway"},
            "declared_purpose": {"kind": "controller", "value": "left_turn_from_highway"},
            "junction_kind": {"kind": "world_setup", "value": "street_intersection"}},
        "deliberate_differences": ["route_relationship", "declared_purpose", "junction_kind"],
        "probe": {"primary_variable": "declared_purpose",
                  "comparison_or_standard": "independent intent versus original lane/route readback",
                  "target_value_or_branch": "left_turn_from_highway"}}
    cases = [baseline]
    params = {
        "turn_from_highway": ("from_highway", "left_turn_from_highway", "street_intersection"),
        "turn_onto_highway": ("onto_highway", "left_turn_onto_highway", "street_intersection"),
        "through_travel": ("from_highway", "through_travel", "street_intersection"),
        "right_turn_purpose": ("from_highway", "right_turn", "street_intersection"),
        "alley_junction_rejection": ("from_highway", "left_turn_from_alley", "alley")}
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        key = case_id.removeprefix(AID + "__")
        route, purpose, junction = params[key]
        cases.append({"case_id": case_id, "paired_probe_id": {
            "turn_onto_highway": "qualifying_turn_directions",
            "through_travel": "purpose_vs_trajectory", "right_turn_purpose": "purpose_vs_trajectory",
            "alley_junction_rejection": "intersection_classification"}.get(key, "qualifying_turn_directions"),
            "rationale": "Source-sealed purpose and measured route/lane contrast without assigned legal outcome.",
            "recording_description": description, "target_law_id": LAW,
            "target_type": "boundary_probe", "unresolved_judgment_calls": [PHRASE],
            "variable_assignments": {
                "route_relationship": {"kind": "world_setup", "value": route},
                "declared_purpose": {"kind": "controller", "value": purpose},
                "junction_kind": {"kind": "world_setup", "value": junction}},
            "deliberate_differences": ["route_relationship", "declared_purpose", "junction_kind"],
            "probe": {"primary_variable": "declared_purpose",
                      "comparison_or_standard": "original lane occupancy, route and pre-entry intent",
                      "target_value_or_branch": purpose}})
    cref = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
                                 "status": "draft", "cases": cases,
                                 "sweep_specs": [{"sweep_id": "purpose_sufficiency_requires_local_review",
                                     "target_law_id": LAW,
                                     "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                                     "status": "incomplete",
                                     "rationale": "No statutory distance or duration cutoff is supplied; source-bound purpose and route require local judgment review.",
                                     "missing_inputs": ["Reviewed original Native route, independently recorded purpose and local purpose-sufficiency judgment."]}],
                                 "sweeps_expanded": True})
    write("semantic-index.json", {
        "format": "worker-semantic-delivery", "assignment_id": AID,
        "source": "Exact NRS 484B.223(3)(a) text and frozen C382162 cell",
        "status": "draft", "stages": {"relevance_batch": rel_batch,
            "relevance": rel, "template": tref, "judgment_observables": [jref],
            "bindings": bref, "cases": cref}})
    return len(cases) - 1


if __name__ == "__main__":
    print(build())
