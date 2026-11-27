"""Build exact-law draft canonical semantic proposals for C227890."""
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
QUOTE = PLAN["law_text"]
TEMPLATE = LAW + "@" + ACTOR


def _write(folder, name, value):
    path = folder / (name + ".json")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def recording_description():
    channels = [{"name": row["name"], "method": row["source"],
                 "unit": "structured original source", "sampling_rate_hz": 20,
                 "reference_frame": "source-reviewed highway and original Native frame map",
                 "time_window": "all 900 original Native frames",
                 "uncertainty": "actual movement safety requires independent legal review"}
                for row in PLAN["observations"]]
    return {"channels": channels,
            "context_inputs": [{"name": "reviewed_parked_highway_packet", "unit": "source",
                                "method": "source-hashed map, dedication, public use, parking rule and Native readback"}],
            "limitations": ["Requested departure timing does not prove original physical outcome.",
                            "Synthetic diagnostics do not establish legal parking or safe movement."]}


def build():
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
                                    "applies_to": [ACTOR], "confidence": "medium",
                                    "relevance_type": "ordinary motor vehicle departing a permitted parked position on a source-qualified highway",
                                    "notes": "Public highway, parking permission, driver and actual approach route need original source review."}],
                 "borderline_excluded": []}
    references = {"relevance": _write(folder, "relevance", relevance),
                  "relevance_batch": _write(folder, "relevance_batch", relevance)}
    judgments = [
        ("stopped, standing or parked on a highway",
         "Selected branch is initially parked; verify highway boundaries, public dedication and original vehicle activity."),
        ("except when stopping, standing or parking where no parking is permitted",
         "Retain location-specific parking rule and original date/time; selected cases require permitted parking."),
        ("unless and until such movement can be made with safety",
         "Measure original trajectories, approach, gap and departure timing; safety has no invented numeric cutoff."),
    ]
    parameters = [
        {"name": "highway_parking_context", "kind": "world_setup",
         "range_or_domain": "source-reviewed public highway and permitted parking bay"},
        {"name": "approach_direction", "kind": "world_setup",
         "range_or_domain": "rear or opposing source-reviewed approach route"},
        {"name": "approach_route_relation", "kind": "world_setup",
         "range_or_domain": "intersecting or nonintersecting actual trajectories"},
        {"name": "departure_policy", "kind": "controller",
         "range_or_domain": "wait until pass, start before pass, clear approach or nonconflicting route"},
    ]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": QUOTE, "parameter_refs": parameters,
                "structure": {
                    "law_id": LAW,
                    "activation": {"condition": "A person controls an ordinary motor vehicle initially parked within a source-qualified highway.",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must_not",
                                   "description": "Do not start the parked vehicle into movement unless and until the movement can be made with safety.",
                                   "numeric_conditions": []},
                    "exceptions": [{"source_clause": "except when stopping, standing or parking where no parking is permitted",
                                    "description": "Outside selected permitted-parking branch; applicable no-parking context requires independent source review."}],
                    "timing": {"description": "Original parked state, approaching vehicle and attempted departure are measured across one 45-second episode.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                              for phrase, note in judgments]}}
    references["template"] = _write(folder, "template", template)
    observations = [entry["name"] for entry in PLAN["observations"]]
    judgment_refs = []
    for index, (phrase, note) in enumerate(judgments, 1):
        requirements = {
            "context_inputs": [{"name": "reviewed_parked_highway_packet", "unit": "source",
                                "description": "Original source-hashed highway, parking, actor and route review."}],
            "landmarks": [],
            "observables": [{"name": name, "unit": "structured original source",
                             "description": "Original sealed 20 Hz source for " + name.replace("_", " ")}
                            for name in observations],
            "recording_needs": [{"name": "four_original_cameras", "unit": "structured original source",
                                 "description": "Four synchronized original Native camera streams."}],
            "sweep_dimensions": [],
            "limitations": ["Actual source review and legal safety interpretation are pending; no numeric legal cutoff is inferred."]}
        judgment_refs.append(_write(folder, "judgment-" + str(index),
                                    {"status": "draft", "template_id": TEMPLATE,
                                     "phrase": phrase, "note": note,
                                     "observable_requirements": requirements}))
    references["judgment_observables"] = judgment_refs
    binding = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
               "context_refs": [],
               "established_contexts": ["Frozen C227890 road, parked departure and other-vehicle control; surveyed site pending."],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "fixed_parameters": [{"name": "reviewed_parked_highway_packet",
                                     "value": "source_packet_pending",
                                     "rationale": "Hold permitted parking, ordinary driver, 45-second cadence and four views fixed."}],
               "variable_parameters": [dict(row, used_by_laws=[LAW]) for row in parameters]}
    references["bindings"] = _write(folder, "bindings", binding)
    description = recording_description()
    cases = []
    for row in PLAN["cases"]:
        values = {"highway_parking_context": "source_reviewed_permitted_highway_parking",
                  "approach_direction": row["approach_direction"],
                  "approach_route_relation": "nonintersecting" if row["variant"] == "opposing_nonconflict" else "intersecting",
                  "departure_policy": row["departure_policy"]}
        assignments = {parameter["name"]: {"kind": parameter["kind"],
                                             "value": values[parameter["name"]]}
                       for parameter in parameters}
        cases.append({"case_id": row["case_id"], "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": row["variant"],
                      "rationale": row["target_description"],
                      "deliberate_differences": [row["deliberate_condition"]],
                      "recording_description": description,
                      "variable_assignments": assignments,
                      "unresolved_judgment_calls": [phrase for phrase, _ in judgments],
                      "probe": {"primary_variable": "departure_policy",
                                "target_value_or_branch": row["variant"],
                                "comparison_or_standard": "other exact parked-departure variants"}})
    baseline = dict(cases[0])
    baseline.update({"case_id": ASSIGNMENT + "__baseline", "target_type": "baseline",
                     "paired_probe_id": "baseline",
                     "rationale": "Shared permitted parking and original capture reference; baseline is not dispatched."})
    references["cases"] = _write(folder, "cases", {"status": "draft", "cell_id": CELL,
                                                  "actor": ACTOR, "cases": [baseline] + cases,
                                                  "sweeps_expanded": True,
                                                  "sweep_specs": [{"sweep_id": "legal_phrase_" + str(index),
                                                                   "target_law_id": LAW, "status": "incomplete",
                                                                   "judgment_refs": [{"phrase": phrase, "note": note}],
                                                                   "rationale": "No accepted original measurement or exact judgment range supplied.",
                                                                   "missing_inputs": ["Original physical and legal review."]}
                                                                  for index, (phrase, note) in enumerate(judgments, 1)]})
    _write(folder, "semantic-index", {"format": "worker-semantic-delivery",
                                      "assignment_id": ASSIGNMENT,
                                      "source": "Exact NRS 484B.410, frozen C227890 cell and original witness",
                                      "status": "draft", "stages": references})


if __name__ == "__main__":
    build()
