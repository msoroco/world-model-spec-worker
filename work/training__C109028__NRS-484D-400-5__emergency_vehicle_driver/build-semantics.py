"""Draft canonical semantic stages from the frozen NRS 484D.400(5) source."""
import hashlib
import json
from pathlib import Path
from batch_pipeline.store import digest

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
    for index, judgment in enumerate(template["structure"]["judgment_calls_needed"]):
        phrase, note = judgment["phrase"], judgment["note"]
        row = {"template_id": template_id, "phrase": phrase, "note": note,
            "status": "draft", "observable_requirements": {
                "observables": [{"name": "siren_source", "unit": "structured",
                                 "description": "Frame-joined independent PCM review and Native approach."}],
                "context_inputs": [{"name": "dispatch_authorization", "unit": "structured",
                                    "description": "Original dispatch, authorization and acoustic documents."}],
                "sweep_dimensions": [{"name": "observer_distance_ft", "unit": "ft",
                    "description": "Documented observer distance in the acoustic source report."}] if index == 0 else
                    [{"name": "other_approach_distance_m", "unit": "m",
                    "description": "Original Native other-vehicle center distance to the authored junction."}],
                "landmarks": [],
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
        "variable_parameters": [
            {"name": "documented_emergency_call", "kind": "world_setup",
             "range_or_domain": "original dispatch fact true or false", "used_by_laws": [law]},
            {"name": "documented_immediate_pursuit", "kind": "world_setup",
             "range_or_domain": "original dispatch fact true or false", "used_by_laws": [law]},
            {"name": "siren_requested", "kind": "controller",
             "range_or_domain": "siren requested true or false", "used_by_laws": [law]},
            {"name": "observer_distance_ft", "kind": "world_setup",
             "range_or_domain": "500 to 600 ft", "used_by_laws": [law]},
            {"name": "other_approach_distance_m", "kind": "world_setup",
             "range_or_domain": "10 to 20 m", "used_by_laws": [law]}]}
    bindings_ref = write("bindings.json", bindings)
    case_path = OUT / "cases.json"
    cases = json.loads(case_path.read_text())
    baseline = json.loads(json.dumps(next(c for c in cases["cases"]
                                          if c["case_id"].endswith("__ordinary_lamps_only"))))
    baseline.update(case_id=HERE.name + "__baseline", target_type="baseline",
                    rationale="Unselected ordinary lamps-only reference for canonical semantic comparison.")
    baseline.pop("paired_probe_id", None)
    baseline.pop("deliberate_differences", None)
    baseline.pop("probe", None)
    cases["cases"].append(baseline)
    sweep_id = "C109028-joint-evidence"
    sweep_cases = [next(c for c in cases["cases"] if c["case_id"].endswith("__sweep_" + str(i)))
                   for i in range(4)]
    axes = [
        {"variable": "observer_distance_ft", "observable": "observer_distance_ft",
         "unit": "ft", "min": 500, "max": 600, "spacing": 100,
         "measurement": {"method": "independent calibrated acoustic report tied to original microphone source hash",
                         "time_window": "full recorded acoustic assessment", "statistic": "first"},
         "range_rationale": "The source clause names 500 feet; 600 feet samples a farther original observer position without a new legal threshold.",
         "spacing_rationale": "Two endpoints test source binding; no interpolation or legal cutoff is inferred.",
         "feasibility_evidence": "The acquisition contract accepts independently documented distances at or beyond 500 feet; CPU fixtures verify both endpoint joins."},
        {"variable": "other_approach_distance_m", "observable": "other_approach_distance_m",
         "unit": "m", "min": 10, "max": 20, "spacing": 10,
         "measurement": {"method": "original Native other vehicle body center to authored intersection center",
                         "time_window": "first original synchronized frame", "statistic": "first"},
         "range_rationale": "Two distinct other-vehicle approach positions in the frozen crossroads sample pursuit proximity evidence without deciding violator status.",
         "spacing_rationale": "The 10 m separation is an authored physical sampling step, not an immediacy or legal threshold.",
         "feasibility_evidence": "The second actor can be spawned at distinct positions on the same authored crossing approach; original Native geometry is retained."},
    ]
    spec = {"sweep_id": sweep_id, "target_law_id": law, "judgment_refs":
            template["structure"]["judgment_calls_needed"], "status": "complete",
            "rationale": "Jointly sample observer distance and other-vehicle approach geometry, retaining original acoustic and incident-source review for legal judgments.",
            "mode": "joint", "landmarks": [], "axes": axes,
            "variable_assignments": sweep_cases[0]["variable_assignments"],
            "recording_description": sweep_cases[0]["recording_description"]}
    spec["spec_version"] = digest(spec)
    spec["planned_case_count"] = 4
    spec["selection_order"] = [c["case_id"] for c in sweep_cases]
    for rank, case in enumerate(sweep_cases):
        case.update(sweep_id=sweep_id, sweep_spec_version=spec["spec_version"],
                    sweep_point={"observer_distance_ft": case["variable_assignments"]["observer_distance_ft"]["value"],
                                 "other_approach_distance_m": case["variable_assignments"]["other_approach_distance_m"]["value"]},
                    selection_rank=rank, judgment_refs=spec["judgment_refs"],
                    sweep_measurements=[{"variable": a["variable"], "observable": a["observable"],
                                         "unit": a["unit"], "measurement": a["measurement"]} for a in axes])
    cases["sweep_specs"] = [spec]
    cases["sweeps_expanded"] = True
    cases_ref = write("cases.json", cases)
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
             "stages": {"relevance_batch": relevance_batch, "relevance": relevance_one,
                        "template": template_ref, "judgment_observables": judgments,
                        "bindings": bindings_ref, "cases": cases_ref}}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    print(json.dumps({"stages": sorted(build()["stages"])}))
