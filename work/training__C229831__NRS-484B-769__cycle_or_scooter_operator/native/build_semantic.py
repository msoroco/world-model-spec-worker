"""Author the draft semantic stage chain for the frozen arm-signal law."""
import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
PROPOSALS = FOLDER / "proposals"
ASSIGNMENT = json.loads((REPO / "inputs" / FOLDER.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
LAW_ID = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
CELL = ASSIGNMENT["cell_id"]
TEMPLATE_ID = LAW_ID + "@" + ACTOR


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    cases = json.loads((PROPOSALS / "cases.json").read_text())
    pair = FOLDER.name + "__arm_method_pair"
    baseline = {"case_id": FOLDER.name + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Unselected roadway bicycle context",
                "variable_assignments": {"cycle_right_turn_hand_signal": {
                    "kind": "controller", "unit": "categorical", "value": None}},
                "recording_description": cases["cases"][0]["recording_description"],
                "unresolved_judgment_calls": []}
    for case in cases["cases"]:
        label = case["case_id"].rsplit("_", 1)[-1]
        value = {"a": "right_horizontal", "b": "none",
                 "c": "left_upward"}[label]
        case["target_type"] = "violating_attempt" if label == "b" else "compliant_attempt"
        case["variable_assignments"]["cycle_right_turn_hand_signal"].update(
            {"unit": "categorical", "value": value})
        case["paired_probe_id"] = pair
        case["deliberate_differences"] = ["cycle_right_turn_hand_signal"]
        case["probe"] = {
            "primary_variable": "cycle_right_turn_hand_signal",
            "comparison_or_standard": "Original arm geometry and pixels for the statutory hand-and-arm methods; no legal finding from fixture",
            "target_value_or_branch": value}
    cases["cases"].insert(0, baseline)
    cases["format"] = "worker-case-proposals"
    cases["law_id"] = LAW_ID
    cases_ref = write("cases.json", cases)
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW_ID, "quote": LAW["text"],
                                    "applies_to": [ACTOR],
                                    "relevance_type": "specific_match",
                                    "confidence": "high",
                                    "notes": "Exact roadway bicycle/e-bike/e-scooter hand-and-arm signaling provision; referenced method reviewed separately."}],
                 "borderline_excluded": []}
    relevance_batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    exception = LAW["text"].split(", except that ", 1)[1]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW_ID,
                "actor": ACTOR, "status": "draft", "quote": LAW["text"],
                "structure": {
                    "activation": {"source_clause": "An operator of a bicycle, an electric bicycle or an electric scooter upon a roadway",
                                   "description": "Observe qualifying rider and full bicycle footprint on the sourced roadway."},
                    "obligation": {"source_clause": "shall give all signals by hand and arm in the manner required by NRS 484B.420 [DEF-NRS-484B-420]",
                                   "description": "Review original limb geometry and four camera streams for a signal; referenced method remains source-reviewed."},
                    "exceptions": [{"source_clause": "except that " + exception,
                                    "description": "Right turn may use horizontal right hand and arm to the right side."}],
                    "timing": {"source_clause": "upon a roadway",
                               "description": "Review the recorded original roadway interval and turn; no duration threshold is inferred."},
                    "judgment_calls_needed": []},
                "parameter_refs": []}
    template_ref = write("template.json", template)
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
               "established_contexts": [],
               "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": "cycle_right_turn_hand_signal",
                                       "kind": "controller",
                                       "range_or_domain": "right_horizontal, none, left_upward request; original arm and pixel observation separate",
                                       "used_by_laws": [LAW_ID]}]}
    binding_ref = write("bindings.json", binding)
    index = {"format": "worker-semantic-delivery",
             "assignment_id": FOLDER.name,
             "stages": {"relevance_batch": relevance_batch_ref,
                        "relevance": relevance_ref, "template": template_ref,
                        "judgment_observables": [], "bindings": binding_ref,
                        "cases": cases_ref}}
    write("semantic-index.json", index)
    print(json.dumps({"draft_stages": 5, "selected_cases": 3,
                      "legal_verdict_claimed": False}))


if __name__ == "__main__":
    main()
