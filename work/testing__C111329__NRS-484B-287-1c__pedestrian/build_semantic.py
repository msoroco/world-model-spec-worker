"""Author the source-gated canonical semantic stage chain for this assignment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / "proposals"
LAW = "NRS-484B-287-1c"
CELL = "C111329"
ACTOR = "pedestrian"
TEMPLATE = LAW + "@" + ACTOR
QUOTE = ("Except as provided in NRS 484B.290 [LVMC-11-30-140-B]: "
         "Between adjacent intersections at which official traffic-control devices "
         "are in operation pedestrians shall not cross at any place except in a marked crosswalk.")
PHRASES = (
    ("adjacent intersections", "walker_crossing_route", "m"),
    ("official traffic-control devices are in operation", "device_operation", "state"),
    ("Except as provided in NRS 484B.290 [LVMC-11-30-140-B]",
     "marking_and_junction_context", "source"),
)
PARAMETERS = (
    ("between_intersections", "world_setup", "source-bound direct segment and crossing station"),
    ("marked_crosswalk_present", "world_setup", "source-surveyed marked extent contains crossing station"),
    ("both_devices_operating", "world_setup", "two source-identified device histories during crossing"),
    ("capture_profile", "world_setup", "four original RGB views, 20 Hz, 900 frames"),
)


def write(path: Path, value) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    common = {"status": "draft", "cell_id": CELL, "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{
        "law_id": LAW, "quote": QUOTE,
        "applies_to": [ACTOR], "confidence": "low",
        "relevance_type": "between-intersections pedestrian crossing",
        "notes": "Original C111329 two-junction site and legal reviews are pending."}],
        borderline_excluded=[])
    relevance_ref = write(PROPOSALS / "relevance.json", relevance)
    batch_ref = write(PROPOSALS / "relevance_batch.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": QUOTE,
        "parameter_refs": [{"name": name, "kind": kind,
                            "range_or_domain": domain}
                           for name, kind, domain in PARAMETERS],
        "structure": {"activation": {"condition": "Pedestrian crosses between source-identified adjacent intersection candidates whose official traffic-control devices are in operation.", "numeric_conditions": []},
            "obligation": {"type": "must_not", "description": "Do not cross outside a marked crosswalk when the source-supported conditions apply.", "numeric_conditions": []},
            "exceptions": [{"source_clause": "Except as provided in NRS 484B.290 [LVMC-11-30-140-B]", "review_status": "source-gated"}],
            "timing": {"description": "Join original crossing to device operation at both endpoints and marked extent.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": "Retain independent source review before a legal finding."}
                                      for phrase, _, _ in PHRASES]}}
    template_ref = write(PROPOSALS / "template.json", template)
    judgments = []
    for index, (phrase, name, unit) in enumerate(PHRASES, 1):
        item = {"name": name, "unit": unit,
                "description": "Original source-bound observation required for the cited phrase."}
        judgment = {"status": "draft", "template_id": TEMPLATE,
            "phrase": phrase, "note": "Retain independent source review before a legal finding.",
            "observable_requirements": {"observables": [item],
                "recording_needs": [item],
                "context_inputs": [{"name": "highway_and_exception_review", "unit": "source",
                    "description": "Independent original highway, official-device and exception review."}],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": ["Original site and legal status are source-gated; appearance alone is insufficient."]}}
        judgments.append(write(PROPOSALS / ("judgment-" + str(index) + ".json"), judgment))
    binding = dict(common, law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}],
        context_refs=[], established_contexts=["Frozen C111329 intersection travel cell; actual two-junction site pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": CELL,
                           "rationale": "Frozen catalog identity, not physical site evidence."}],
        variable_parameters=[{"name": name, "kind": kind,
            "range_or_domain": domain, "used_by_laws": [LAW]}
            for name, kind, domain in PARAMETERS])
    binding_ref = write(PROPOSALS / "bindings.json", binding)
    case_rows = []
    baseline = plan["cases"][0]
    for index, case in enumerate([baseline] + plan["cases"]):
        is_baseline = index == 0
        cid = ROOT.name + "__semantic_baseline" if is_baseline else case["case_id"]
        short = case["case_id"].split("__")[-1]
        config = json.loads((ROOT / "cases" / short / "config.json").read_text())
        marked = case["scenario_parameters"]["marked_crosswalk_present"]
        operating = case["scenario_parameters"]["both_devices_operating"]
        values = {"between_intersections": "source-bound direct segment and crossing station",
            "marked_crosswalk_present": marked,
            "both_devices_operating": operating,
            "capture_profile": "four original RGB views, 20 Hz, 900 frames"}
        row = {"case_id": cid, "target_law_id": None if is_baseline else LAW,
            "target_type": "baseline" if is_baseline else "boundary_probe",
            "rationale": "Neutral comparison anchor; no separate recording." if is_baseline else case["purpose"],
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                                     for name, kind, _ in PARAMETERS},
            "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES],
            "recording_description": config["case"]["recording_description"]}
        if not is_baseline:
            variable = "both_devices_operating" if not operating else "marked_crosswalk_present"
            row.update(paired_probe_id="operation_probe" if not operating else "marking_probe",
                deliberate_differences=[variable],
                probe={"primary_variable": variable,
                    "comparison_or_standard": "same source-bound site, crossing station and capture profile",
                    "target_value_or_branch": values[variable]})
        case_rows.append(row)
    sweep = {"sweep_id": "source-gated-judgment-coverage", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase,
                           "note": "Retain independent source review before a legal finding."}
                          for phrase, _, _ in PHRASES],
        "rationale": "No numeric judgment sweep can be selected without the reviewed original site and legal source.",
        "status": "incomplete",
        "missing_inputs": ["reviewed original C111329 two-junction source",
                           "official-device authority and operation review",
                           "NRS 484B.290 exception review"]}
    write(PROPOSALS / "pending-source-judgment-sweep.json", sweep)
    cases_ref = write(PROPOSALS / "cases.json", dict(common, sweep_specs=[sweep],
        sweeps_expanded=True,
        sweep_expansion_scope="Three selected physical boundary probes are enumerated; original-source judgment remains incomplete.",
        cases=case_rows))
    write(PROPOSALS / "semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ROOT.name,
        "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgments,
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    build()
    print("source-gated semantic chain authored")
