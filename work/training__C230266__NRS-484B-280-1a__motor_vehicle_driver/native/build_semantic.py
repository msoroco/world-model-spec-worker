"""Build source-bound draft semantic proposals for the selected pedestrian pair."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / "proposals"
LAW = "NRS-484B-280-1a"
ACTOR = "motor_vehicle_driver"
CELL = "C230266"
PHRASE = "Exercise due care to avoid a collision with a pedestrian."
NOTE = "Source motion and response are diagnostic; due care remains a legal judgment."


def write(name, value):
    path = PROPOSALS / (name + ".json")
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": PHRASE,
                                    "applies_to": [ACTOR], "relevance_type": "general_duty",
                                    "confidence": "high",
                                    "notes": "The frozen road and pedestrian cell supplies the stated parties; actual encounter requires original capture."}],
                 "borderline_excluded": []}
    template = {"template_id": LAW + "@" + ACTOR, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": PHRASE,
                "structure": {"activation": {"condition": "motor vehicle driver and pedestrian encounter",
                                             "numeric_conditions": []},
                              "obligation": {"type": "exercise_due_care",
                                             "description": "avoid collision with a pedestrian",
                                             "source_clause": PHRASE,
                                             "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "during the pedestrian encounter",
                                         "numeric_conditions": []},
                              "judgment_calls_needed": [{"phrase": PHRASE, "note": NOTE}]},
                "parameter_refs": [{"name": "pedestrian_conflict_response", "kind": "controller",
                                    "range_or_domain": "distance-triggered slow request or maintain request"}]}
    observable = {"template_id": template["template_id"], "phrase": PHRASE,
                  "note": NOTE, "status": "draft",
                  "observable_requirements": {
                      "observables": [{"name": "rel.surface_gap", "unit": "m",
                                       "description": "Original body separation over the encounter"},
                                      {"name": "rel.contact", "unit": "structured",
                                       "description": "Original vehicle collision sensor events"},
                                      {"name": "kin.speed", "unit": "m/s",
                                       "description": "Original vehicle speed response"}],
                      "context_inputs": [{"name": "pedestrian_path_survey", "unit": "structured",
                                          "description": "Original map and independent pedestrian path survey"}],
                      "sweep_dimensions": [], "landmarks": [],
                      "recording_needs": [{"name": "ru.pedestrian", "unit": "structured",
                                           "description": "Pedestrian identity and sampled movement"},
                                          {"name": "rel.contact", "unit": "structured",
                                           "description": "Original collision-event stream"}],
                      "limitations": ["No speed, gap, braking or time-to-conflict cutoff defines legal due care.",
                                      "Original Native pixels and physical motion require review."]}}
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": [{"name": "road_pedestrian_cell",
                                         "source": "frozen catalog C230266"}],
               "law_refs": [{"template_id": template["template_id"],
                              "binding_kind": "general_duty"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": "pedestrian_conflict_response",
                                        "kind": "controller",
                                        "range_or_domain": "distance-triggered slow request or maintain request",
                                        "used_by_laws": [LAW]}]}
    cases = json.loads((PROPOSALS / "cases.json").read_text())
    selected = [item for item in cases["cases"] if item["target_type"] != "baseline"]
    description = selected[0]["recording_description"]
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": LAW,
                "target_type": "baseline", "rationale": "Shared source context for selected response comparison",
                "variable_assignments": {"pedestrian_conflict_response":
                                         {"kind": "controller", "value": "maintain_request", "unit": "categorical"}},
                "recording_description": description,
                "unresolved_judgment_calls": [PHRASE]}
    cases["status"] = "draft"
    cases["cases"] = [baseline] + selected
    for case in selected:
        case["unresolved_judgment_calls"] = [PHRASE]
    cases["sweep_specs"] = [{"sweep_id": "c230266-pedestrian-response",
                             "target_law_id": LAW,
                             "judgment_refs": [{"phrase": PHRASE, "note": NOTE}],
                             "rationale": "Categorical response pair retains legal judgment for original review.",
                             "status": "incomplete",
                             "missing_inputs": ["A numeric physical sweep axis cannot represent this categorical controller comparison without changing the selected case contract."]}]
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
