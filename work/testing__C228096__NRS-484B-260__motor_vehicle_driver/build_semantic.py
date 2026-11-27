"""Build source-grounded draft stage proposals for private-way yielding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ASSIGNMENT = PLAN["assignment_id"]
LAW = PLAN["law_id"]
CELL = PLAN["cell_id"]
ACTOR = PLAN["actor"]
TEMPLATE = LAW + "@" + ACTOR


def save(folder, name, value):
    path = folder / (name + ".json")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": PLAN["law_text"],
                                    "applies_to": [ACTOR], "confidence": "medium",
                                    "relevance_type": "ordinary driver entering or crossing highway from a source-qualified private way",
                                    "notes": "Private origin, public destination, every approaching vehicle and original precedence require source review."}],
                 "borderline_excluded": []}
    refs = {"relevance": save(folder, "relevance", relevance),
            "relevance_batch": save(folder, "relevance_batch", relevance)}
    judgments = [
        ("about to enter or cross a highway from a private way",
         "Confirm original private ownership and access, public highway designation, feasible route and driver control."),
        ("all vehicles approaching on such highway",
         "Inventory every highway actor on both source-reviewed approach directions at each original frame."),
        ("yield the right-of-way",
         "Measure original vehicle trajectories, times and precedence; legal yielding has no invented numeric cutoff."),
    ]
    parameters = [
        {"name": "private_way_origin", "kind": "world_setup", "range_or_domain": "source-reviewed private ownership and permitted use"},
        {"name": "maneuver", "kind": "world_setup", "range_or_domain": "enter or cross reviewed highway connection"},
        {"name": "approach_sides", "kind": "world_setup", "range_or_domain": "left, right, both or no approaching actor"},
        {"name": "ego_control_policy", "kind": "controller", "range_or_domain": "yield all, continue, or yield one of two"},
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": PLAN["law_text"], "parameter_refs": parameters,
                "structure": {
                    "law_id": LAW,
                    "activation": {"condition": "An ordinary driver is about to enter or cross a public highway from a source-qualified private way.",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must", "description": "Yield the right-of-way to all vehicles approaching on that highway.",
                                   "numeric_conditions": []},
                    "exceptions": [],
                    "timing": {"description": "Original approach and ego movement are measured through one 45-second episode.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for phrase, note in judgments]}}
    refs["template"] = save(folder, "template", template)
    requirement = {
        "context_inputs": [{"name": "reviewed_private_way_site_packet", "unit": "source record",
                            "description": "Original source-hashed private way, highway, route and actor review."}],
        "landmarks": [],
        "observables": [{"name": row["name"], "unit": "source record",
                         "description": "Original sealed 20 Hz source for " + row["name"].replace("_", " ")}
                        for row in PLAN["observations"]],
        "recording_needs": [{"name": "four_camera_original_pixels", "unit": "source record",
                             "description": "Four synchronized original Native camera streams."}],
        "sweep_dimensions": [],
        "limitations": ["Actual physical source review and legal yielding interpretation are pending; no numeric legal cutoff is inferred."],
    }
    refs["judgment_observables"] = [save(folder, "judgment-" + str(index), {
        "status": "draft", "template_id": TEMPLATE, "phrase": phrase, "note": note,
        "observable_requirements": requirement})
        for index, (phrase, note) in enumerate(judgments, 1)]
    binding = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
               "context_refs": [],
               "established_contexts": ["Frozen C228096 private-way road-entry witness; original site review pending."],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "fixed_parameters": [{"name": "reviewed_private_way_site_packet",
                                     "value": "source_packet_pending",
                                     "rationale": "Hold private origin, public destination, ordinary driver and 20 Hz four-view episode fixed."}],
               "variable_parameters": [dict(row, used_by_laws=[LAW]) for row in parameters]}
    refs["bindings"] = save(folder, "bindings", binding)
    cases = []
    for row in PLAN["cases"]:
        construction = json.loads((ROOT / "cases" / row["variant"] / "construction.json").read_text())
        values = row["draft_variables"]
        assignments = {parameter["name"]: {"kind": parameter["kind"],
                                             "value": values.get(parameter["name"], "source_reviewed")}
                       for parameter in parameters}
        cases.append({"case_id": row["case_id"], "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": row["variant"],
                      "rationale": row["target_description"],
                      "deliberate_differences": [row["deliberate_condition"]],
                      "recording_description": construction["recording_description"],
                      "variable_assignments": assignments,
                      "unresolved_judgment_calls": [phrase for phrase, _ in judgments],
                      "probe": {"primary_variable": "ego_control_policy",
                                "target_value_or_branch": row["variant"],
                                "comparison_or_standard": "other exact private-way variants"}})
    baseline = dict(cases[0])
    baseline.update({"case_id": ASSIGNMENT + "__baseline", "target_type": "baseline",
                     "paired_probe_id": "baseline",
                     "rationale": "Shared source-reviewed private-way and highway capture reference; baseline is not dispatched."})
    refs["cases"] = save(folder, "cases", {
        "status": "draft", "cell_id": CELL, "actor": ACTOR, "cases": [baseline] + cases,
        "sweeps_expanded": True,
        "sweep_specs": [{"sweep_id": "legal_phrase_" + str(index),
                         "target_law_id": LAW, "status": "incomplete",
                         "judgment_refs": [{"phrase": phrase, "note": note}],
                         "rationale": "No accepted original measurement or exact judgment range supplied.",
                         "missing_inputs": ["Original physical and legal review."]}
                        for index, (phrase, note) in enumerate(judgments, 1)]})
    save(folder, "semantic-index", {"format": "worker-semantic-delivery",
                                    "assignment_id": ASSIGNMENT,
                                    "source": "Exact NRS 484B.260, frozen C228096 cell and original witness",
                                    "status": "draft", "stages": refs})


if __name__ == "__main__":
    build()
