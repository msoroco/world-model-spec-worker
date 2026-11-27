"""Build the exact-law draft stage chain for local canonical adoption."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
LAW = ASSIGNMENT["law"]
LAW_ID = ASSIGNMENT["law_id"]
ACTOR = ASSIGNMENT["actor"]
CELL_ID = ASSIGNMENT["cell_id"]
TEMPLATE_ID = LAW_ID + "@" + ACTOR
PROPOSALS = ROOT / "proposals"


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    law_text = LAW["text"]
    relevance = {"cell_id": CELL_ID, "actor": ACTOR, "status": "draft",
                 "relevant_laws": [{"law_id": LAW_ID, "quote": law_text,
                                    "applies_to": [ACTOR], "relevance_type": "specific_match",
                                    "confidence": "medium",
                                    "notes": "Actual bus class, loading, designated place and emergency require original review."}],
                 "borderline_excluded": []}
    references = {"relevance_batch": write("relevance_batch.json", relevance),
                  "relevance": write("relevance.json", relevance)}
    judgments = [
        ("other than a tour bus", "Original class or permit record must identify excluded tour buses."),
        ("for the purpose of loading or unloading passengers or their baggage",
         "Original door, passenger and baggage evidence must establish actual loading purpose."),
        ("which has been designated in accordance with Section 11.60.010 [DEF-LVMC-11-60-010]",
         "A designation authority record for the assigned route endpoint is not supplied."),
        ("except in case of an emergency", "Emergency facts require independent original review.")]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": ACTOR,
                "status": "draft", "quote": law_text,
                "structure": {"activation": {"source_clause": "The operator of a bus, other than a tour bus",
                                             "description": "Identify the bus and actual class from original records."},
                              "obligation": {"source_clause": "Not stop such vehicle upon any street at any place for the purpose of loading or unloading passengers or their baggage",
                                             "description": "Join a stopped bus to actual loading and the precise original place."},
                              "exceptions": [{"source_clause": "except in case of an emergency",
                                              "description": "Preserve the emergency exception as a separate original-facts review."}],
                              "timing": {"source_clause": "for the purpose of loading or unloading passengers or their baggage",
                                         "description": "Join loading evidence to the stopped interval using original frame times."},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note in judgments]},
                "parameter_refs": []}
    references["template"] = write("template.json", template)
    terms = ["ru.tour_bus_or_limousine", "sig.door_open", "st.curb_zone", "sig.hazard"]
    observable_refs = []
    for index, ((phrase, note), term) in enumerate(zip(judgments, terms)):
        item = {"name": term, "unit": "structured",
                "description": "Retain original source and independent review of " + phrase + "."}
        value = {"template_id": TEMPLATE_ID, "phrase": phrase, "note": note,
                 "status": "draft",
                 "observable_requirements": {"observables": [item], "context_inputs": [],
                                             "sweep_dimensions": [], "landmarks": [],
                                             "recording_needs": [item],
                                             "limitations": [note, "Synthetic fixtures cannot establish original legal facts."]}}
        observable_refs.append(write("judgment_observables_" + str(index) + ".json", value))
    references["judgment_observables"] = observable_refs
    binding = {"cell_id": CELL_ID, "actor": ACTOR, "status": "draft",
               "established_contexts": [],
               "law_refs": [{"template_id": TEMPLATE_ID, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": "requested_loading_branch", "kind": "world_setup",
                                        "range_or_domain": "eight exact requested statutory alternatives",
                                        "used_by_laws": [LAW_ID]}]}
    references["bindings"] = write("bindings.json", binding)
    proposal_path = PROPOSALS / "cases.json"
    proposal = json.loads(proposal_path.read_text())
    proposal["status"] = "draft"
    proposal["cases"] = [case for case in proposal["cases"] if case["target_type"] != "baseline"]
    proposal["sweep_specs"] = [{"sweep_id": "bus-original-designation-and-loading-review",
                                 "target_law_id": LAW_ID, "status": "incomplete",
                                 "judgment_refs": [{"phrase": p, "note": n} for p, n in judgments],
                                 "rationale": "Eight exact requested branch constructions are selected; original authority and actual loading review remain open.",
                                 "missing_inputs": ["Original Native pixels and passenger transfer review",
                                                    "Original designation authority under Section 11.60.010",
                                                    "Original bus class and emergency records"]}]
    for case in proposal["cases"]:
        slug = case["case_id"].removeprefix(ROOT.name + "__")
        case["target_type"] = "judgment_sweep"
        case["variable_assignments"] = {"requested_loading_branch": {"kind": "world_setup", "value": slug}}
        case["unresolved_judgment_calls"] = [phrase for phrase, _ in judgments]
        case["paired_probe_id"] = "bus-branch-comparison"
        case["deliberate_differences"] = ["requested_loading_branch"]
        case["probe"] = {"primary_variable": "requested_loading_branch",
                         "comparison_or_standard": "source-bound reference case",
                         "target_value_or_branch": slug}
    baseline = dict(proposal["cases"][0])
    baseline["case_id"] = ROOT.name + "__baseline"
    baseline["target_law_id"] = None
    baseline["target_type"] = "baseline"
    baseline["rationale"] = "Unselected shared context for the canonical stage contract."
    baseline["variable_assignments"] = {"requested_loading_branch": {"kind": "world_setup", "value": None}}
    baseline.pop("probe", None)
    baseline.pop("paired_probe_id", None)
    baseline.pop("deliberate_differences", None)
    proposal["cases"].insert(0, baseline)
    references["cases"] = write("cases.json", proposal)
    write("semantic-index.json", {"format": "worker-semantic-delivery",
                                  "assignment_id": ROOT.name, "stages": references})
    print("semantic stages written", len(proposal["cases"]))


if __name__ == "__main__":
    main()
