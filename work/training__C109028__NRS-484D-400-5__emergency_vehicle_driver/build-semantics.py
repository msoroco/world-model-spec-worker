"""Draft canonical semantic stages from the frozen NRS 484D.400(5) source."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE.parents[1] / "inputs" / HERE.name / "assignment.json"
OUT = HERE / "proposals"


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads(INPUT.read_text())
    quote = assignment["law"]["text"]
    law, actor, cell = assignment["law_id"], assignment["actor"], assignment["cell_id"]
    template_id = law + "@" + actor
    relevance = {"cell_id": cell, "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote,
            "applies_to": [actor], "relevance_type": "specific_match",
            "confidence": "high", "notes":
            "The frozen cell assigns an emergency vehicle driver in an intersection response."}],
        "borderline_excluded": []}
    relevance_batch = write("relevance_batch.json", relevance)
    relevance_one = write("relevance.json", relevance)
    template = {"template_id": template_id, "law_id": law, "actor": actor,
        "status": "draft", "quote": quote, "structure": {
            "activation": {"source_clause": "An authorized emergency vehicle",
                "description": "Authorization and actor identity require independent original source records."},
            "obligation": {"source_clause": "the siren must not be used except when the vehicle is operated in response to an emergency call or in the immediate pursuit of an actual or suspected violator of the law",
                "description": "Observe siren output and response or pursuit source on the same original frame window."},
            "exceptions": [
                {"source_clause": "when the vehicle is operated in response to an emergency call",
                 "description": "Documented emergency-call operation is a qualifying siren-use branch."},
                {"source_clause": "in the immediate pursuit of an actual or suspected violator of the law",
                 "description": "Documented immediate pursuit is the alternative qualifying branch."},
                {"source_clause": "may operate the vehicle’s warning lamps without sounding the siren",
                 "description": "Measure lamp and siren independently in a lamps-only branch."}],
            "timing": {"source_clause": "when the vehicle is operated in response to an emergency call or in the immediate pursuit",
                       "description": "Compare source-grounded response intervals with the audible siren interval."},
            "judgment_calls_needed": [
                {"phrase": "under normal conditions", "note":
                 "Equipment audibility at 500 feet requires a qualified original acoustic assessment."},
                {"phrase": "actual or suspected violator of the law", "note":
                 "Pursuit purpose and the factual status of a suspected violator require original dispatch and incident sources."}]},
        "parameter_refs": []}
    template_ref = write("template.json", template)
    judgments = []
    for index, (phrase, note) in enumerate((
        ("under normal conditions", "Qualified 500-foot acoustic assessment remains a source question."),
        ("actual or suspected violator of the law", "Dispatch and incident purpose require independent review."))):
        row = {"template_id": template_id, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": {
                "observables": [{"name": "siren_source", "unit": "structured",
                                 "description": "Frame-joined independent PCM review and Native approach."}],
                "context_inputs": [{"name": "dispatch_authorization", "unit": "structured",
                                    "description": "Original dispatch, authorization and acoustic documents."}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": "siren_source", "unit": "structured",
                                     "description": "Retained PCM and per-frame review."}],
                "limitations": ["Synthetic CPU evidence proves software joins only.",
                                "No engineering amplitude cutoff decides statutory audibility or pursuit status."]}}
        judgments.append(write(f"judgment_observables_{index}.json", row))
    bindings = {"cell_id": cell, "actor": actor, "status": "draft",
        "established_contexts": [], "law_refs": [{"template_id": template_id,
                                                  "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [{"name": "crossroads_route",
            "kind": "world_setup", "value": "same 600-frame four-way approach",
            "used_by_laws": [law]}],
        "variable_parameters": [{"name": "siren_and_response_branch",
            "kind": "controller", "range_or_domain":
            "call siren, ordinary siren, pursuit siren, call lamps only, ordinary lamps only",
            "used_by_laws": [law]}]}
    bindings_ref = write("bindings.json", bindings)
    case_path = OUT / "cases.json"
    cases = json.loads(case_path.read_text())
    cases.setdefault("sweep_specs", [])
    cases.setdefault("sweeps_expanded", [])
    cases_ref = write("cases.json", cases)
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
             "stages": {"relevance_batch": relevance_batch, "relevance": relevance_one,
                        "template": template_ref, "judgment_observables": judgments,
                        "bindings": bindings_ref, "cases": cases_ref}}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    print(json.dumps({"stages": sorted(build()["stages"])}))
