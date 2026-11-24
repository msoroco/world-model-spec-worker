"""Generate and validate source-grounded draft law stages before case coverage.

This writes only law relevance, template, judgment observations and cell binding.
The canonical case stage and complete semantic index remain pending.
"""

import hashlib
import json
import os
from pathlib import Path

from construction import POLICIES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate():
    if ".runtime-work" not in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""):
        raise ValueError("Set runtime output root under .runtime-work before validation")
    from batch_pipeline import stages

    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text(encoding="utf-8"))
    law, cell, actor = assignment["law"], assignment["cell"], assignment["actor"]
    law_id = assignment["law_id"]
    template_id = law_id + "@" + actor
    request = {"cell": cell, "actor": actor}
    common = {"request": request, "law_records": {law_id: law}, "dependencies": []}
    quote = law["text"]
    relevance = {"cell_id": cell["cell_id"], "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law_id, "quote": quote,
                    "applies_to": [actor], "confidence": "low",
                    "relevance_type": "conditional left-turn opposite-direction yield and reciprocal duty",
                    "notes": "Opposing position and actor response require retained Native evidence; legal judgments remain unresolved."}],
                 "borderline_excluded": []}
    stages.validate("relevance_batch", relevance, common)
    stages.validate("relevance", relevance, common)
    write(ROOT / "proposals/relevance_batch.json", relevance)
    write(ROOT / "proposals/relevance.json", relevance)
    phrases = [
        ("immediate hazard", "Approach proximity and speed are observable; legal hazard judgment remains open."),
        ("yield the right-of-way", "Original trajectories and control response are measurable; legal priority is not inferred."),
        ("when and as required", "Original signal state is measurable; the separate signal requirement must be sourced."),
    ]
    parameters = [
        ("opponent_initial_position", "world_setup", "within intersection versus approaching outside"),
        ("initial_yield_controller", "controller", "wait versus proceed before initial opponent clears"),
        ("ego_left_signal_controller", "controller", "request left signal versus omit signal"),
        ("later_opponent_response_controller", "controller", "later opposing actor waits versus proceeds"),
        ("commanded_turn_path", "controller", "connected left-turn waypoint plan"),
        ("commanded_approach_speed", "controller", "finite positive approach speed in m/s"),
    ]
    template = {"template_id": template_id, "law_id": law_id, "actor": actor,
                "quote": quote,
                "structure": {"law_id": law_id,
                    "activation": {"condition": "Vehicle within a source-reviewed intersection intends to turn left.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "Yield to an opposite-direction vehicle within the intersection or constituting an immediate hazard.",
                                   "type": "must", "numeric_conditions": []},
                    "exceptions": [{"source_clause": "having so yielded and having given a signal when and as required, may make such left turn",
                                    "description": "Conditional permission and later reciprocal duty; not an assumed legal exception.",
                                    "trigger": "Yield and applicable signal duty are established",
                                    "effect": "Left-turn permission becomes available",
                                    "replacement_obligation": "Later opposite-direction vehicles yield to the turning vehicle"}],
                    "timing": {"description": "Observe initial approach, yield, turn commitment and later opposing approach separately.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note in phrases]},
                "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                                   for name, kind, domain in parameters]}
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    stages.validate("template", template, {"request": {"law_id": law_id, "actor": actor},
                    "law_record": law, "canonical_parameter_rules": rules,
                    "dependencies": []})
    write(ROOT / "proposals/template.json", template)
    observations = [
        ("opponent_body_history", "Opposite-direction body position and temporal proximity."),
        ("ego_body_history", "Left-turn subject body, movement and relative timing."),
        ("ego_signal_history", "Observed left-signal state and timing."),
    ]
    for index, ((phrase, note), (name, description)) in enumerate(zip(phrases, observations), 1):
        needs = {"observables": [{"name": name, "unit": "structured" if name != "ego_signal_history" else "categorical",
                                  "description": description}],
                 "context_inputs": [{"name": "intersection_geometry", "unit": "structured",
                                     "description": "Source-reviewed intersection boundary and approach identity."}],
                 "sweep_dimensions": [], "landmarks": [],
                 "recording_needs": [{"name": name, "unit": "structured" if name != "ego_signal_history" else "categorical",
                                      "description": description}],
                 "limitations": ["Raw observations do not decide this qualitative statutory phrase."]}
        proposal = {"template_id": template_id, "phrase": phrase, "note": note,
                    "status": "draft", "observable_requirements": needs}
        stages.validate("judgment_observables", proposal,
                        {"request": {"template_id": template_id, "phrase": phrase, "note": note},
                         "dependencies": []})
        write(ROOT / f"proposals/judgment-{index}.json", proposal)
    binding = {"cell_id": cell["cell_id"], "actor": actor, "status": "draft",
               "established_contexts": ["Assigned intersection and left-turn cell; physical Native source review pending"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
               "context_refs": [],
               "fixed_parameters": [{"name": "assigned_intersection_identity",
                                      "value": cell["cell_id"],
                                      "rationale": "Frozen catalog assignment; physical map identity still pending"}],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain,
                                        "used_by_laws": [law_id]}
                                       for name, kind, domain in parameters]}
    stages.validate("bindings", binding, {"request": dict(request, template_ids=[template_id]),
                    "canonical_parameter_rules": rules, "dependencies": [template]})
    write(ROOT / "proposals/bindings.json", binding)
    recording = json.loads((ROOT / "proposals/cases.json").read_text(encoding="utf-8"))["cases"][0]["recording_description"]
    base_values = {"opponent_initial_position": "inside",
                   "initial_yield_controller": True,
                   "ego_left_signal_controller": True,
                   "later_opponent_response_controller": None,
                   "commanded_turn_path": "connected left turn",
                   "commanded_approach_speed": 5.0}
    kinds = {item["name"]: item["kind"] for item in binding["variable_parameters"]}

    def assignments(values):
        return {name: {"kind": kinds[name], "value": value} for name, value in values.items()}

    joined_template = json.loads(json.dumps(template))
    for index, call in enumerate(joined_template["structure"]["judgment_calls_needed"], 1):
        call["observable_requirements"] = json.loads(
            (ROOT / f"proposals/judgment-{index}.json").read_text(encoding="utf-8"))["observable_requirements"]
    cases = [{"case_id": assignment["assignment_id"] + "__semantic_baseline",
              "target_law_id": None, "target_type": "baseline",
              "rationale": "Shared setup reference; no legal conclusion or separate recording planned.",
              "variable_assignments": assignments(base_values),
              "unresolved_judgment_calls": [item[0] for item in phrases],
              "recording_description": recording}]
    pair = {"inside_yield": ("initial_within_yield", "initial_yield_controller"),
            "inside_no_yield": ("initial_within_yield", "initial_yield_controller"),
            "approaching_yield": ("approaching_hazard_yield", "initial_yield_controller"),
            "approaching_no_yield": ("approaching_hazard_yield", "initial_yield_controller"),
            "signal_given": ("signal_condition", "ego_left_signal_controller"),
            "signal_omitted": ("signal_condition", "ego_left_signal_controller"),
            "reciprocal_yield": ("reciprocal_duty", "later_opponent_response_controller"),
            "reciprocal_no_yield": ("reciprocal_duty", "later_opponent_response_controller")}
    for suffix, (position, wait, signal, later) in POLICIES.items():
        values = dict(base_values, opponent_initial_position=position,
                      initial_yield_controller=wait, ego_left_signal_controller=signal,
                      later_opponent_response_controller=later)
        pair_id, variable = pair[suffix]
        cases.append({"case_id": assignment["assignment_id"] + "__" + suffix,
                      "target_law_id": law_id, "target_type": "boundary_probe",
                      "rationale": "Case-specific observed response; no legal cutoff or result presumed: " + suffix,
                      "variable_assignments": assignments(values),
                      "paired_probe_id": pair_id,
                      "deliberate_differences": [variable],
                      "probe": {"primary_variable": variable,
                                "comparison_or_standard": pair_id,
                                "target_value_or_branch": str(values[variable])},
                      "unresolved_judgment_calls": [item[0] for item in phrases],
                      "recording_description": recording})
    sweep_specs = [{"sweep_id": "pending-" + str(i), "target_law_id": law_id,
                    "judgment_refs": [{"phrase": phrase, "note": note}],
                    "status": "incomplete", "mode": "one_dimensional", "axes": [],
                    "landmarks": [], "rationale": "Source-grounded judgment observation; physical range not yet defensible.",
                    "variable_assignments": assignments(base_values),
                    "recording_description": recording,
                    "missing_inputs": ["Reviewed Native junction and feasible physical range for qualitative sweep"]}
                   for i, (phrase, note) in enumerate(phrases, 1)]
    case_proposal = {"cell_id": cell["cell_id"], "actor": actor, "status": "draft",
                     "cases": cases, "sweep_specs": sweep_specs}
    stages.validate("cases", case_proposal,
                    {"request": request, "dependencies": [binding], "templates": [joined_template]})
    write(ROOT / "proposals/cases.json", case_proposal)
    files = ("relevance_batch.json", "relevance.json", "template.json",
             "judgment-1.json", "judgment-2.json", "judgment-3.json", "bindings.json",
             "cases.json")
    index = {"format": "worker-semantic-draft-stage-index",
             "assignment_id": assignment["assignment_id"],
             "canonical_case_stage_validated": True,
             "stages": {name: sha(ROOT / "proposals" / name) for name in files}}
    write(ROOT / "proposals/semantic-draft-stage-index.json", index)
    references = {name: {"path": "proposals/" + filename,
                         "sha256": sha(ROOT / "proposals" / filename)}
                  for name, filename in (("relevance_batch", "relevance_batch.json"),
                                         ("relevance", "relevance.json"),
                                         ("template", "template.json"),
                                         ("bindings", "bindings.json"),
                                         ("cases", "cases.json"))}
    references["judgment_observables"] = [
        {"path": f"proposals/judgment-{i}.json",
         "sha256": sha(ROOT / f"proposals/judgment-{i}.json")}
        for i in range(1, 4)]
    semantic_index = {"format": "worker-semantic-delivery",
                      "assignment_id": assignment["assignment_id"],
                      "stages": references}
    write(ROOT / "proposals/semantic-index.json", semantic_index)
    from worker_exchange import semantic_delivery
    manifest = json.loads((ROOT / "execution-manifest.json").read_text(encoding="utf-8"))
    index["canonical_validation"] = semantic_delivery.validate(ROOT, assignment, manifest)
    write(ROOT / "proposals/semantic-draft-stage-index.json", index)
    return index


if __name__ == "__main__":
    result = generate()
    print(json.dumps({"validated_draft_stages": len(result["stages"]),
                      "canonical_case_stage_validated": True}))
