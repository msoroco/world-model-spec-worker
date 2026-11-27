"""Build draft canonical right-curb proposals from the exact frozen case plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
LAW = PLAN["law_id"]
CELL = PLAN["cell_id"]
ACTOR = PLAN["actor"]
TEMPLATE = LAW + "@" + ACTOR
JUDGMENTS = [
    ("upon a highway where there are adjacent curbs", "Review public highway and adjacent right curb from original site sources."),
    ("parallel", "Original wheel-axis/curb angle is measured; the statute supplies no numerical parallel tolerance."),
    ("Except as otherwise provided in this section", "Review location-specific left-curb and angle-parking ordinances and DOT status."),
]
PARAMETERS = [
    {"name": "right_wheel_distance_inches", "kind": "world_setup", "range_or_domain": "17, 18 or 19 inch target from reviewed right curb"},
    {"name": "parallel_angle_target_deg", "kind": "world_setup", "range_or_domain": "0 or 8 degree construction target; no legal cutoff"},
    {"name": "activity", "kind": "controller", "range_or_domain": "original park or stop"},
]


def _write(folder, name, value):
    path = folder / (name + ".json")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def recording_description():
    channels = [{"name": row["name"], "method": row["source"],
                 "unit": "structured original source", "sampling_rate_hz": 20,
                 "reference_frame": "source-reviewed right curb and original Native frame map",
                 "time_window": "all 900 original Native frames",
                 "uncertainty": "physical visibility and legal interpretation require independent review"}
                for row in PLAN["observations"]]
    return {"channels": channels,
            "context_inputs": [{"name": "reviewed_right_curb_site", "unit": "source",
                                "method": "source-hashed highway, curb, ordinance and vehicle review"}],
            "limitations": ["Requested wheel pose does not prove actual Native position.",
                            "Synthetic diagnostics do not establish physical or legal compliance."]}


def build():
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    relevance = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
                 "relevant_laws": [{"law_id": LAW, "quote": PLAN["law_text"],
                                    "applies_to": [ACTOR], "confidence": "medium",
                                    "relevance_type": "ordinary motor vehicle stopped or parked at a source-reviewed adjacent right curb",
                                    "notes": "Original highway, curb, ordinance applicability, wheels and activity need source review."}],
                 "borderline_excluded": []}
    refs = {"relevance": _write(folder, "relevance", relevance),
            "relevance_batch": _write(folder, "relevance_batch", relevance)}
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
                "quote": PLAN["law_text"], "parameter_refs": PARAMETERS,
                "structure": {"law_id": LAW,
                    "activation": {"condition": "An ordinary vehicle is stopped or parked on a source-qualified highway with adjacent curbs.",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must", "description": "Keep right-hand wheels parallel to and within 18 inches of the right-hand curb under the selected default branch.",
                                   "numeric_conditions": [{"variable": "right_wheel_curb_distance", "operator": "<=", "value": 18, "unit": "in"}]},
                    "exceptions": [{"source_clause": "Local authorities may by ordinance permit parking of vehicles with the left-hand wheels adjacent to and within 18 inches of the left-hand curb of a one-way highway.",
                                    "description": "Review location-specific left-curb ordinance applicability; not selected here."},
                                   {"source_clause": "Local authorities may by ordinance permit angle parking on any highway",
                                    "description": "Review angle-parking ordinance and Department highway determination; not selected here."}],
                    "timing": {"description": "Original 20 Hz stopped or parked interval within a 45-second episode.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": note} for phrase, note in JUDGMENTS]}}
    refs["template"] = _write(folder, "template", template)
    observations = [row["name"] for row in PLAN["observations"]]
    judgment_refs = []
    for index, (phrase, note) in enumerate(JUDGMENTS, 1):
        needs = {"context_inputs": [{"name": "reviewed_right_curb_site", "unit": "source",
                                    "description": "Original map, dedication, curb survey, ordinance, DOT status and blueprint."}],
                 "landmarks": [],
                 "observables": [{"name": name, "unit": "structured original source",
                                  "description": "Sealed original source for " + name.replace("_", " ")}
                                 for name in observations],
                 "recording_needs": [{"name": "four_camera_original_pixels", "unit": "structured original source",
                                      "description": "Four synchronized original Native camera streams."}],
                 "sweep_dimensions": [],
                 "limitations": ["Legal interpretation and actual pixel visibility require independent original review."]}
        judgment_refs.append(_write(folder, "judgment-" + str(index),
                                    {"status": "draft", "template_id": TEMPLATE,
                                     "phrase": phrase, "note": note,
                                     "observable_requirements": needs}))
    refs["judgment_observables"] = judgment_refs
    binding = {"status": "draft", "cell_id": CELL, "actor": ACTOR,
               "context_refs": [],
               "established_contexts": ["Frozen C214875 residence district, parallel parking and right-curb cell; original site pending."],
               "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
               "fixed_parameters": [{"name": "reviewed_right_curb_site", "value": "source_packet_pending",
                                     "rationale": "Hold highway, ordinary vehicle, curb, cadence and four views fixed."}],
               "variable_parameters": [dict(row, used_by_laws=[LAW]) for row in PARAMETERS]}
    refs["bindings"] = _write(folder, "bindings", binding)
    description = recording_description()
    cases = []
    for row in PLAN["cases"]:
        values = row["draft_variables"]
        is_distance_probe = row["variant"] in ("park_17in_parallel", "park_18in_parallel", "park_19in_parallel")
        primary_variable = ("right_wheel_distance_inches" if is_distance_probe else
                            "parallel_angle_target_deg" if row["variant"].endswith("skew") else "activity")
        probe = {"primary_variable": primary_variable,
                 "target_value_or_branch": values[primary_variable],
                 "comparison_or_standard": "other exact right-curb variants"}
        if is_distance_probe:
            probe.update({"threshold_ref": "obligation.numeric_conditions[0]",
                          "operator": "<=", "unit": "in",
                          "test_value": values["right_wheel_distance_inches"]})
        cases.append({"case_id": row["case_id"], "target_law_id": LAW,
                      "target_type": "boundary_probe", "paired_probe_id": "eighteen_inch_boundary" if is_distance_probe else row["variant"],
                      "rationale": row["target_description"],
                      "deliberate_differences": [primary_variable],
                      **({"epsilon_used": {"value": 1, "unit": "in",
                                          "rationale": "One-inch engineering probes below, at and above the exact statutory distance."}}
                         if is_distance_probe else {}),
                      "recording_description": description,
                      "variable_assignments": {p["name"]: {"kind": p["kind"], "value": values[p["name"]]}
                                               for p in PARAMETERS},
                      "unresolved_judgment_calls": [phrase for phrase, _ in JUDGMENTS],
                      "probe": probe})
    baseline = dict(cases[0])
    baseline.update({"case_id": PLAN["assignment_id"] + "__baseline", "target_type": "baseline",
                     "paired_probe_id": "baseline", "rationale": "Shared source-qualified right-curb reference; baseline is not dispatched."})
    refs["cases"] = _write(folder, "cases", {"status": "draft", "cell_id": CELL,
                                            "actor": ACTOR, "cases": [baseline] + cases,
                                            "sweeps_expanded": True,
                                            "sweep_specs": [{"sweep_id": "legal_phrase_" + str(index),
                                                             "target_law_id": LAW, "status": "incomplete",
                                                             "judgment_refs": [{"phrase": phrase, "note": note}],
                                                             "rationale": "No accepted original judgment range or physical calibration supplied.",
                                                             "missing_inputs": ["Original physical and legal review."]}
                                                            for index, (phrase, note) in enumerate(JUDGMENTS, 1)]})
    _write(folder, "semantic-index", {"format": "worker-semantic-delivery",
                                        "assignment_id": PLAN["assignment_id"],
                                        "source": "Exact NRS 484B.457(1), frozen C214875 cell and original witness",
                                        "status": "draft", "stages": refs})


if __name__ == "__main__":
    build()
