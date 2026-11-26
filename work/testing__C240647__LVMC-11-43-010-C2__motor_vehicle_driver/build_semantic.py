"""Author the exact U-turn canonical semantic stage proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "LVMC-11-43-010-C1"
CELL = "C133321"
ACTOR = "motor_vehicle_driver"
QUOTE = ("The following regulations pertain to the operation of vehicles within a roundabout: "
         "The operator of a vehicle who intends to exit a roundabout: Shall use the left lane "
         "to turn left or complete a U-turn.")
TEMPLATE = LAW + "@" + ACTOR
PHRASE = "left lane"
NOTE = "Review source-mapped allocated lanes and original actor lane occupation during the U-turn."


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
                                    "relevance_type": "intended U-turn exit and allocated left lane",
                                    "confidence": "medium",
                                    "notes": "Actual map allocation and U-turn completion remain for original Native review."}],
                 "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": QUOTE,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Operator intends a U-turn exit from a roundabout.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Use the left lane to complete the U-turn.",
                                             "type": "must", "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "Observe allocated lane throughout circular traversal and actual opposite-direction departure.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [{"name": "roundabout_lane_role", "kind": "world_setup",
                                    "range_or_domain": "source-mapped left or outer circular lane"}]}
    temp_ref = write("template.json", template)
    judgment = {"template_id": TEMPLATE, "phrase": PHRASE, "note": NOTE, "status": "draft",
                "observable_requirements": {"observables": [{"name": "original_ring_lane_history",
                                                        "unit": "structured",
                                                        "description": "Original map-associated actor lane and section readback."}],
                                            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                                            "recording_needs": [{"name": "original_roundabout_topology",
                                                                 "unit": "structured",
                                                                 "description": "Original allocated-lane map readback."}],
                                            "limitations": ["Map allocation and legal left-lane meaning require local source review."]}}
    jref = write("judgment-1.json", judgment)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": ["Frozen multilane roundabout U-turn cell; actual site and allocation pending review."],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "fixed_parameters": [{"name": "reviewed_roundabout_site", "value": "source_packet_pending",
                                     "rationale": "Hold the same source map, entry and opposite exit across both cases."}],
               "variable_parameters": [{"name": "roundabout_lane_role", "kind": "world_setup",
                                        "range_or_domain": "source-mapped left or outer circular lane",
                                        "used_by_laws": [LAW]}]}
    bref = write("bindings.json", binding)
    description = json.loads((HERE / "cases/left_lane_u_turn/construction.json").read_text())["recording_description"]
    baseline = {"case_id": AID + "__baseline", "paired_probe_id": "baseline",
                "rationale": "Shared map and operator reference for the lane-use comparison.",
                "recording_description": description, "target_law_id": LAW,
                "target_type": "baseline", "unresolved_judgment_calls": [PHRASE],
                "variable_assignments": {"roundabout_lane_role": {"kind": "world_setup", "value": "left"}},
                "deliberate_differences": ["roundabout_lane_role"],
                "probe": {"primary_variable": "roundabout_lane_role",
                          "comparison_or_standard": "source-bound left versus outer lane",
                          "target_value_or_branch": "left"}}
    cases = [baseline]
    for entry in manifest["cases"]:
        case = entry["case_id"]
        role = "left" if case.endswith("__left_lane_u_turn") else "outer"
        cases.append({"case_id": case, "paired_probe_id": "u_turn_left_vs_outer_lane",
                      "rationale": "Measure original allocated circular lane and opposite-direction departure without prelabeling legal outcome.",
                      "recording_description": description, "target_law_id": LAW,
                      "target_type": "boundary_probe", "unresolved_judgment_calls": [PHRASE],
                      "variable_assignments": {"roundabout_lane_role": {"kind": "world_setup", "value": role}},
                      "deliberate_differences": ["roundabout_lane_role"],
                      "probe": {"primary_variable": "roundabout_lane_role",
                                "comparison_or_standard": "source-bound left versus outer lane",
                                "target_value_or_branch": role}})
    proposed = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                "cases": cases,
                "sweep_specs": [{"sweep_id": "mapped_left_lane_review", "target_law_id": LAW,
                                 "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                                 "status": "incomplete",
                                 "rationale": "Physical allocation and legal application cannot be resolved by a numeric worker cutoff.",
                                 "missing_inputs": ["Original Native allocated-lane map and legal review of left-lane meaning."]}],
                "sweeps_expanded": True}
    cref = write("cases.json", proposed)
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "source": "Exact LVMC 11.43.010(C)(1) text and C133321 frozen cell",
             "status": "draft", "stages": {"relevance_batch": rel_batch,
                                             "relevance": rel, "template": temp_ref,
                                             "judgment_observables": [jref],
                                             "bindings": bref, "cases": cref}}
    write("semantic-index.json", index)
    return len(cases) - 1


if __name__ == "__main__":
    print(build())
