"""Author source-scoped canonical semantic proposals for the exact intersection cell."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def put(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate():
    if ".runtime-work" not in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""):
        raise ValueError("Set pipeline output root under .runtime-work")
    from batch_pipeline import stages
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    law, cell, actor = assignment["law"], assignment["cell"], assignment["actor"]
    law_id = assignment["law_id"]
    template_id = law_id + "@" + actor
    request = {"cell": cell, "actor": actor}
    quote = law["text"]
    relevance = {"cell_id": cell["cell_id"], "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law_id, "quote": quote, "applies_to": [actor],
                    "confidence": "low", "relevance_type": "intersection stop, stand or park and source-limited exceptions",
                    "notes": "Native intersection boundary, activity and exception context remain pending original review."}],
                 "borderline_excluded": []}
    common = {"request": request, "law_records": {law_id: law}, "dependencies": []}
    for name in ("relevance_batch", "relevance"):
        stages.validate(name, relevance, common)
        put(ROOT / "proposals" / (name + ".json"), relevance)
    judgments = [
        ("stop, stand or park", "Original motion does not alone establish the legal activity class."),
        ("Within an intersection", "Original body footprint needs a reviewed highway intersection boundary."),
        ("necessary to avoid conflict with other traffic", "Necessity needs independent traffic observations."),
        ("in compliance with law", "A specific applicable law and compliance need independent source."),
        ("directions of a police officer or official traffic-control device", "The original direction and compliance need independent observation."),
    ]
    parameters = [
        ("destination", "world_setup", "outside or inside reviewed intersection boundary"),
        ("activity_request", "controller", "intentional stop, stand, park or through movement"),
        ("exception_setup", "world_setup", "none, traffic conflict, law, officer or device source"),
        ("approach_route", "world_setup", "reviewed connected incoming lane and destination"),
        ("capture_profile", "world_setup", "four original RGB views, 20 Hz, 900 frames"),
    ]
    template = {"template_id": template_id, "law_id": law_id, "actor": actor, "quote": quote,
                "structure": {"law_id": law_id,
                    "activation": {"condition": "Person stops, stands or parks a vehicle within a source-reviewed intersection.", "numeric_conditions": []},
                    "obligation": {"description": "Do not stop, stand or park within an intersection absent a statutory exception.", "type": "must_not", "numeric_conditions": []},
                    "exceptions": [
                        {"source_clause": "necessary to avoid conflict with other traffic", "description": "Traffic necessity is independently observed.", "trigger": "Necessary traffic conflict", "effect": "Prohibition exception may apply"},
                        {"source_clause": "in compliance with law", "description": "A specific applicable law is independently sourced.", "trigger": "Compliance with law", "effect": "Prohibition exception may apply"},
                        {"source_clause": "directions of a police officer", "description": "Police direction and compliance are independently observed.", "trigger": "Compliant police direction", "effect": "Prohibition exception may apply"},
                        {"source_clause": "official traffic-control device", "description": "Official device direction and compliance are independently observed.", "trigger": "Compliant official device direction", "effect": "Prohibition exception may apply"}],
                    "timing": {"description": "Observe original body, motion, activity and context for the full 900-frame interval.", "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": p, "note": n} for p, n in judgments]},
                "parameter_refs": [{"name": n, "kind": k, "range_or_domain": d} for n, k, d in parameters]}
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    stages.validate("template", template, {"request": {"law_id": law_id, "actor": actor}, "law_record": law,
                    "canonical_parameter_rules": rules, "dependencies": []})
    put(ROOT / "proposals/template.json", template)
    observable_names = ["activity_history", "body_footprint_history", "traffic_conflict_history",
                        "applicable_law_source", "direction_history"]
    for i, ((phrase, note), name) in enumerate(zip(judgments, observable_names), 1):
        unit = "structured"
        needs = {"observables": [{"name": name, "unit": unit, "description": note}],
                 "context_inputs": [{"name": "intersection_geometry", "unit": "structured",
                                     "description": "Reviewed Native map, approach and intersection boundary."}],
                 "sweep_dimensions": [], "landmarks": [],
                 "recording_needs": [{"name": name, "unit": unit, "description": note}],
                 "limitations": ["Original observations do not decide this qualitative statutory phrase."]}
        proposal = {"template_id": template_id, "phrase": phrase, "note": note,
                    "status": "draft", "observable_requirements": needs}
        stages.validate("judgment_observables", proposal,
                        {"request": {"template_id": template_id, "phrase": phrase, "note": note}, "dependencies": []})
        put(ROOT / f"proposals/judgment-{i}.json", proposal)
    binding = {"cell_id": cell["cell_id"], "actor": actor, "status": "draft",
               "established_contexts": ["Assigned stop/stand intersection cell; Native site and exceptions remain source-gated"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}], "context_refs": [],
               "fixed_parameters": [{"name": "assigned_cell", "value": cell["cell_id"],
                                     "rationale": "Frozen catalog cell, not a reviewed physical site"}],
               "variable_parameters": [{"name": n, "kind": k, "range_or_domain": d, "used_by_laws": [law_id]}
                                       for n, k, d in parameters]}
    stages.validate("bindings", binding, {"request": dict(request, template_ids=[template_id]),
                    "canonical_parameter_rules": rules, "dependencies": [template]})
    put(ROOT / "proposals/bindings.json", binding)
    recording = {"channels": [{"name": name, "unit": "structured", "method": "source-sealed original Native sample",
                               "sampling_rate_hz": 20, "time_window": "full original 900-frame interval",
                               "reference_frame": "original CARLA world frame", "uncertainty": "original source and legal review pending"}
                              for name in observable_names if name != "applicable_law_source"],
                 "context_inputs": [{"name": "intersection_geometry", "unit": "structured", "method": "source-sealed reviewed Native map packet"},
                                    {"name": "applicable_law_source", "unit": "structured", "method": "independently reviewed applicable law packet"}],
                 "limitations": ["The original Native site and legal exception sources remain unreviewed.",
                                 "A diagnostic fixture cannot establish physical completion or a legal outcome."]}
    base = {"destination": "inside", "activity_request": "intentional stop", "exception_setup": "none",
            "approach_route": "reviewed incoming lane", "capture_profile": "four RGB 20 Hz 900 frames"}
    kinds = {n: k for n, k, _ in parameters}
    def assignments(values):
        return {n: {"kind": kinds[n], "value": v} for n, v in values.items()}
    cases = [{"case_id": assignment["assignment_id"] + "__semantic_baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Shared setup reference without a separate recording or legal conclusion.",
              "variable_assignments": assignments(base), "unresolved_judgment_calls": [p for p, _ in judgments],
              "recording_description": recording}]
    pair = {"outside_reference": ("boundary_contact", "destination"),
            "inside_stop": ("boundary_contact", "destination"),
            "inside_stand": ("activity_stop_stand", "activity_request"),
            "inside_park": ("activity_stop_park", "activity_request"),
            "traffic_conflict": ("traffic_necessity", "exception_setup"),
            "law_direction": ("law_direction", "exception_setup"),
            "officer_direction": ("officer_direction", "exception_setup"),
            "device_direction": ("device_direction", "exception_setup"),
            "through_motion": ("transient_motion", "activity_request")}
    for row in plan["cases"]:
        suffix = row["case_id"].removeprefix(assignment["assignment_id"] + "__")
        pair_id, variable = pair[suffix]
        values = dict(base, destination=row["body_destination"], activity_request=row["activity_intent"],
                      exception_setup=row["exception_context"])
        cases.append({"case_id": row["case_id"], "target_law_id": law_id,
                      "target_type": "boundary_probe", "rationale": "Source-dependent original observation probe: " + suffix,
                      "variable_assignments": assignments(values), "paired_probe_id": pair_id,
                      "deliberate_differences": [variable],
                      "probe": {"primary_variable": variable, "comparison_or_standard": pair_id,
                                "target_value_or_branch": str(values[variable])},
                      "unresolved_judgment_calls": [p for p, _ in judgments],
                      "recording_description": recording})
    joined = json.loads(json.dumps(template))
    for i, call in enumerate(joined["structure"]["judgment_calls_needed"], 1):
        call["observable_requirements"] = json.loads((ROOT / f"proposals/judgment-{i}.json").read_text())["observable_requirements"]
    sweeps = [{"sweep_id": "pending-" + str(i), "target_law_id": law_id,
               "judgment_refs": [{"phrase": phrase, "note": note}], "status": "incomplete", "mode": "one_dimensional",
               "axes": [], "landmarks": [], "rationale": "Await reviewed Native site and independent context for feasible sweep.",
               "variable_assignments": assignments(base), "recording_description": recording,
               "missing_inputs": ["Reviewed Native intersection and source-grounded feasible range"]}
              for i, (phrase, note) in enumerate(judgments, 1)]
    proposal = {"cell_id": cell["cell_id"], "actor": actor, "status": "draft",
                "cases": cases, "sweep_specs": sweeps}
    stages.validate("cases", proposal, {"request": request, "dependencies": [binding], "templates": [joined]})
    put(ROOT / "proposals/cases.json", proposal)
    names = ("relevance_batch", "relevance", "template", "bindings", "cases")
    refs = {name: {"path": "proposals/" + name + ".json",
                   "sha256": sha(ROOT / "proposals" / (name + ".json"))} for name in names}
    refs["judgment_observables"] = [{"path": f"proposals/judgment-{i}.json",
                                     "sha256": sha(ROOT / f"proposals/judgment-{i}.json")}
                                    for i in range(1, len(judgments) + 1)]
    put(ROOT / "proposals/semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": assignment["assignment_id"], "stages": refs})
    return {"stage_count": len(names) + len(judgments), "selected_cases": len(cases) - 1,
            "index_sha256": sha(ROOT / "proposals/semantic-index.json")}


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True))
