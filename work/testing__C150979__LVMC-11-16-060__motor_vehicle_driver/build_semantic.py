"""Author exact speed/default and posted-exception semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "proposals"
AID = HERE.name
LAW = "LVMC-11-16-060"
CELL = "C150979"
ACTOR = "motor_vehicle_driver"
QUOTE = ("The prima facie speed limit is twenty-five miles per hour on all streets and "
         "highways unless a different speed limit is posted as set forth in this Title.")
TEMPLATE = LAW + "@" + ACTOR
PHRASE = "prima facie"
NOTE = "Retain rebuttal and incorporated Title posting authority for local legal review."


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
                                    "relevance_type": "covered one-way road and prima facie speed/posting",
                                    "confidence": "medium",
                                    "notes": "Municipal jurisdiction and Title posting authority remain for original review."}],
                 "borderline_excluded": []}
    rel_batch = write("relevance_batch.json", relevance)
    rel = write("relevance.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": QUOTE,
                "structure": {"law_id": LAW,
                              "activation": {"condition": "Vehicle travels on a covered street or highway.",
                                             "numeric_conditions": []},
                              "obligation": {"description": "Prima facie limit of 25 miles per hour absent a different applicable posting.",
                                             "type": "limit", "numeric_conditions": [{"value": 25, "unit": "mph"}]},
                              "exceptions": [{"source_clause": "unless a different speed limit is posted as set forth in this Title",
                                              "description": "A different speed limit posted as set forth in this Title.",
                                              "numeric_conditions": []}],
                              "timing": {"description": "Observe speed along governed travel and sign passage.",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [{"name": "requested_speed_mph", "kind": "controller",
                                    "range_or_domain": "20, 25 or 30 mph"},
                                   {"name": "reviewed_posted_limit_mph", "kind": "world_setup",
                                    "range_or_domain": "same-value 25 or different 35 mph"}]}
    temp_ref = write("template.json", template)
    judgment = {"template_id": TEMPLATE, "phrase": PHRASE, "note": NOTE, "status": "draft",
                "observable_requirements": {"observables": [{"name": "original_ego_speed", "unit": "structured",
                                                        "description": "Original actor velocity-derived speed over governed travel."}],
                                            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                                            "recording_needs": [{"name": "original_sign_inventory", "unit": "structured",
                                                                 "description": "Original complete posted-sign inventory and source review."}],
                                            "limitations": ["Prima facie rebuttal and Title posting authority require local legal review."]}}
    jref = write("judgment-1.json", judgment)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": ["Frozen one-way travel and speed-limit sign cell; actual site authority pending review."],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [],
               "fixed_parameters": [{"name": "reviewed_speed_site", "value": "source_packet_pending",
                                     "rationale": "Hold reviewed road, route and municipal site across comparisons."}],
               "variable_parameters": [{"name": "requested_speed_mph", "kind": "controller",
                                        "range_or_domain": "20, 25 or 30 mph", "used_by_laws": [LAW]},
                                       {"name": "reviewed_posted_limit_mph", "kind": "world_setup",
                                        "range_or_domain": "25 or 35 mph", "used_by_laws": [LAW]}]}
    bref = write("bindings.json", binding)
    description = json.loads((HERE / "cases/same25_below/construction.json").read_text())["recording_description"]
    baseline = {"case_id": AID + "__baseline", "paired_probe_id": "baseline",
                "rationale": "Shared original road, sign and actor reference for requested-speed sweep.",
                "recording_description": description, "target_law_id": LAW,
                "target_type": "baseline", "unresolved_judgment_calls": [PHRASE],
                "variable_assignments": {"requested_speed_mph": {"kind": "controller", "value": 25},
                                         "reviewed_posted_limit_mph": {"kind": "world_setup", "value": 25}},
                "deliberate_differences": ["requested_speed_mph"],
                "probe": {"primary_variable": "requested_speed_mph",
                          "comparison_or_standard": "observed original speed across 25 mph",
                          "target_value_or_branch": 25}}
    cases = [baseline]
    for entry in manifest["cases"]:
        case = entry["case_id"]
        key = case.removeprefix(AID + "__")
        target = 20 if key.endswith("below") else 25 if key.endswith("at") else 30
        posting = 35 if key == "different35" else 25
        cases.append({"case_id": case,
                      "paired_probe_id": "different_posted_exception" if key == "different35" else "same_value_25_speed_boundary",
                      "rationale": "Measure original velocity and source-complete posting without prelabeling legal outcome.",
                      "recording_description": description, "target_law_id": LAW,
                      "target_type": "boundary_probe", "unresolved_judgment_calls": [PHRASE],
                      "variable_assignments": {"requested_speed_mph": {"kind": "controller", "value": target},
                                               "reviewed_posted_limit_mph": {"kind": "world_setup", "value": posting}},
                      "deliberate_differences": ["requested_speed_mph", "reviewed_posted_limit_mph"],
                      "probe": {"primary_variable": "requested_speed_mph" if posting == 25 else "reviewed_posted_limit_mph",
                                "comparison_or_standard": "25 mph prima facie boundary and different posted exception",
                                "target_value_or_branch": target if posting == 25 else posting}})
    proposed = {"cell_id": CELL, "actor": ACTOR, "status": "draft", "cases": cases,
                "sweep_specs": [{"sweep_id": "prima_facie_25_mph", "target_law_id": LAW,
                                 "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                                 "status": "incomplete",
                                 "rationale": "Physical speed and legal prima facie interpretation remain for local review.",
                                 "missing_inputs": ["Original governed speed and Title posting authority."]}],
                "sweeps_expanded": True}
    cref = write("cases.json", proposed)
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "source": "Exact LVMC 11.16.060 text and C150979 frozen cell",
             "status": "draft", "stages": {"relevance_batch": rel_batch,
                                         "relevance": rel, "template": temp_ref,
                                         "judgment_observables": [jref],
                                         "bindings": bref, "cases": cref}}
    write("semantic-index.json", index)
    return len(cases) - 1


if __name__ == "__main__":
    print(build())
