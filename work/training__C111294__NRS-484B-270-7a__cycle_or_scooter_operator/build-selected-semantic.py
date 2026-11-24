"""Prepare exact-source canonical stages without inferring intent or a verdict."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-270-7a"
ACTOR = "cycle_or_scooter_operator"
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = HERE / "proposals" / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return {"path": path.relative_to(HERE).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    assert quote == plan["source_law"]["text"]
    description = json.loads((HERE / "v2-primary/witness_1/construction.json").read_text())["recording_description"]
    relevance = {"cell_id": "C111294", "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                                     "relevance_type": "specific_match", "confidence": "medium",
                                     "notes": "Witness narrows to bicycle; original propulsion, motor vehicle class and intent need review."}],
                 "borderline_excluded": []}
    judgments = [
        ("operator of a bicycle, an electric bicycle or an electric scooter",
         "Original vehicle class, wheel configuration, propulsion and rider relation require review."),
        ("Intentionally interfere with the movement of a motor vehicle",
         "Intent and legal interference cannot be inferred from a kinematic reaction alone."),
    ]
    for phrase, _ in judgments:
        assert phrase in quote
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "status": "draft", "quote": quote,
                "structure": {
                    "activation": {"source_clause": judgments[0][0],
                                   "description": "Rider is operating a qualifying bicycle and a separate motor vehicle moves."},
                    "obligation": {"source_clause": judgments[1][0],
                                   "description": "Keep intentional interference as an independent judgment; retain movement response."},
                    "exceptions": [],
                    "timing": {"source_clause": judgments[1][0],
                               "description": "No numeric statutory timing or mandatory reaction-order cutoff is supplied."},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for phrase, note in judgments]},
                "parameter_refs": []}
    units = {row["name"]: row["unit"] for row in description["channels"]}
    observables = []
    for index, ((phrase, note), channel) in enumerate(zip(judgments,
                                                          ("bicycle_body_pose", "motorist_brake"))):
        item = {"name": channel, "unit": units[channel],
                "description": "Original Native and video source for independent judgment."}
        value = {"template_id": TEMPLATE, "phrase": phrase, "note": note,
                 "status": "draft", "observable_requirements": {
                     "observables": [item], "context_inputs": [], "sweep_dimensions": [],
                     "landmarks": [], "recording_needs": [item],
                     "limitations": [note, "Synthetic CPU rows do not establish original conduct or legal state."]}}
        observables.append(write(f"judgment_observables_{index}.json", value))
    binding = {"cell_id": "C111294", "actor": ACTOR, "status": "draft",
               "established_contexts": [], "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": "bicycle_path_intervention", "kind": "controller",
                                        "range_or_domain": "hold before conflict or enter before motorist crossing",
                                        "used_by_laws": [LAW]}]}
    cases = [{"case_id": HERE.name + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Unselected common intersection context.",
              "variable_assignments": {"bicycle_path_intervention": {
                  "kind": "controller", "value": None}},
              "recording_description": description,
              "unresolved_judgment_calls": [phrase for phrase, _ in judgments]}]
    for case, value in zip(plan["cases"], ("hold_before_conflict", "enter_before_motorist")):
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
                      "target_type": "judgment_sweep",
                      "rationale": "Source-shaped bicycle path change versus measured motorist response; intent remains open.",
                      "paired_probe_id": "c111294-bicycle-path-pair",
                      "deliberate_differences": ["bicycle_path_intervention"],
                      "probe": {"primary_variable": "bicycle_path_intervention",
                                "comparison_or_standard": "separate original rider and motorist motion",
                                "target_value_or_branch": value},
                      "variable_assignments": {"bicycle_path_intervention": {
                          "kind": "controller", "value": value}},
                      "recording_description": description,
                      "unresolved_judgment_calls": [phrase for phrase, _ in judgments]})
    proposal = {"cell_id": "C111294", "actor": ACTOR, "status": "draft",
                "cases": cases, "sweeps_expanded": True,
                "sweep_specs": [{"sweep_id": "c111294-intent-and-class-review",
                                 "target_law_id": LAW, "status": "incomplete",
                                 "judgment_refs": [{"phrase": phrase, "note": note}
                                                   for phrase, note in judgments],
                                 "rationale": "Two synthetic movement probes prepared; original actor class and intent remain unresolved.",
                                 "missing_inputs": ["Original Native bicycle and motor vehicle identity",
                                                    "Independent original conduct and intent review"]}]}
    stages = {"relevance_batch": write("relevance_batch.json", relevance),
              "relevance": write("relevance.json", relevance),
              "template": write("template.json", template),
              "judgment_observables": observables,
              "bindings": write("bindings.json", binding),
              "cases": write("cases.json", proposal)}
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": HERE.name, "stages": stages})
    print(json.dumps({"selected_cases": 2, "judgments": len(judgments)}))


if __name__ == "__main__":
    main()
