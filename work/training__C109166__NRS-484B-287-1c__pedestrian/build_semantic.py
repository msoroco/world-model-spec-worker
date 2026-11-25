"""Draft canonical stages for exact 287(1)(c) source review."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "NRS-484B-287-1c"
TEMPLATE = LAW + "@pedestrian"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = HERE / "proposals" / (name + ".json")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(HERE)), "sha256": sha(path)}


def build():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    quote = assignment["law"]["text"]
    desc = json.loads((HERE / "config.json").read_text())["recording_description"]
    judgments = [
        ("Between adjacent intersections",
         "Original Native junction and lane topology plus independent adjacency review; distance alone cannot establish adjacency.",
         ["st.intersection", "st.lane_enters"], False),
        ("at which official traffic-control devices are in operation",
         "Both official control actors must be operating at original pedestrian roadway entry.",
         ["dev.traffic_signal", "st.intersection"], False),
        ("except in a marked crosswalk",
         "Original marked polygon and full pedestrian footprint at roadway entry require independent pixel review.",
         ["st.crosswalk", "rel.occupies", "st.roadway", "kin.position"], False),
        ("Except as provided in NRS 484B.290 [LVMC-11-30-140-B]",
         "Exact exception text and person-specific applicability are absent from the frozen package.",
         ["ru.pedestrian"], True),
    ]
    refs = []
    for index, (phrase, note, names, context) in enumerate(judgments):
        needs = [{"name": name,
                  "unit": next(channel["unit"] for channel in desc["channels"] if channel["name"] == name),
                  "description": "Retain original Native source observations for independent review."}
                 for name in names]
        contexts = ([{"name": "nrs_484b_290_exception", "unit": "source",
                      "description": "Retain source-bound unresolved cross-referenced exception context."}]
                    if context else [])
        refs.append(write("judgment_observables_" + str(index), {
            "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {"observables": needs, "context_inputs": contexts,
                "sweep_dimensions": [], "landmarks": [], "recording_needs": needs,
                "limitations": [note, "Synthetic diagnostics cannot settle physical or legal facts."]}}))
    relevance = {"cell_id": "C109166", "actor": "pedestrian", "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": ["pedestrian"],
                           "relevance_type": "specific_match", "confidence": "medium",
                           "notes": "Original adjacency, operation, marking and NRS 484B.290 remain for review."}],
        "borderline_excluded": []}
    relevance_batch = write("relevance_batch", relevance)
    relevance_ref = write("relevance", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": "pedestrian",
        "status": "draft", "quote": quote,
        "structure": {"activation": {
            "description": "Pedestrian crosses between adjacent intersections with controls in operation.",
            "source_clause": "Between adjacent intersections at which official traffic-control devices are in operation"},
            "obligation": {
            "description": "Measure entry into roadway relative to an original marked crosswalk.",
            "source_clause": "pedestrians shall not cross at any place except in a marked crosswalk."},
            "exceptions": [{"source_clause": "Except as provided in NRS 484B.290 [LVMC-11-30-140-B]",
                            "description": "Person-specific exception requires independent original review."}],
            "timing": {"description": "Join footprint entry with both device operating states and marked crossing source.",
                       "source_clause": "pedestrians shall not cross at any place except in a marked crosswalk."},
            "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                      for phrase, note, _, _ in judgments]},
        "parameter_refs": []}
    template_ref = write("template", template)
    binding = {"cell_id": "C109166", "actor": "pedestrian", "status": "draft",
        "established_contexts": [],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "crossing_location", "kind": "world_setup",
                                 "range_or_domain": "marked_crosswalk or unmarked_midblock",
                                 "used_by_laws": [LAW]}]}
    binding_ref = write("bindings", binding)
    cases = json.loads((HERE / "proposals" / "cases.json").read_text())
    cases["cases"] = [case for case in cases["cases"]
                      if case["case_id"] != HERE.name + "__baseline"]
    baseline = {"case_id": HERE.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Neutral fixed-cell reference; no selected recording",
        "variable_assignments": {"crossing_location": {"kind": "world_setup", "value": None}},
        "unresolved_judgment_calls": [phrase for phrase, _, _, _ in judgments],
        "recording_description": desc}
    cases["cases"].insert(0, baseline)
    for case in cases["cases"][1:]:
        case["variable_assignments"].pop("exception_484b_290", None)
        case["target_type"] = "judgment_sweep"
        case["paired_probe_id"] = "c109166-between-intersections-crossing-location"
        case["deliberate_differences"] = ["crossing_location"]
        case["probe"] = {"primary_variable": "crossing_location",
            "comparison_or_standard": "original full-body roadway entry relative to marked crosswalk",
            "target_value_or_branch": case["variable_assignments"]["crossing_location"]["value"]}
        case["unresolved_judgment_calls"] = [phrase for phrase, _, _, _ in judgments]
    cases["sweeps_expanded"] = True
    cases["sweep_specs"] = [{"sweep_id": "c109166-adjacent-controls-crossing-review",
        "target_law_id": LAW, "status": "incomplete",
        "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note, _, _ in judgments],
        "rationale": "Controlled marked versus unmarked crossing locations; original authority remains for review.",
        "missing_inputs": ["Independently reviewed Native map adjacency and original lane topology",
                           "Original official control operation and marked-crossing pixels",
                           "NRS 484B.290 exact source and person-specific applicability"]}]
    cases_ref = write("cases", cases)
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
             "stages": {"relevance_batch": relevance_batch, "relevance": relevance_ref,
                        "template": template_ref, "judgment_observables": refs,
                        "bindings": binding_ref, "cases": cases_ref}}
    index_path = HERE / "proposals" / "semantic-index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"judgments": len(judgments), "semantic_index_sha256": sha(index_path)}))


if __name__ == "__main__":
    build()
