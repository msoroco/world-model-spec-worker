"""Author source-gated LVMC 11.43.010(B) semantic stage proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / "proposals"
LAW = "LVMC-11-43-010-B"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PHRASES = (
    ("entering a roundabout", "ego_roundabout_entry", "frame"),
    ("vehicles already in the roundabout", "circulating_vehicle_presence", "state"),
    ("yield the right-of-way", "entry_conflict_motion", "m"),
    ("wait for a gap in traffic before entering", "observed_preentry_gap", "s"),
)
PARAMETERS = (
    ("opponent_lane_relation", "world_setup", "connected or adjacent circulating lane"),
    ("planned_gap_condition", "world_setup", "near or wider requested initial gap"),
    ("ego_entry_request", "world_setup", "wait or enter control request"),
    ("capture_profile", "world_setup", "four original RGB views, 20 Hz, 900 frames"),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": "C130864", "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low",
        "relevance_type": "roundabout entry and already-present vehicle",
        "notes": "Actual source-reviewed Native map, lane connectivity, vehicle routes and jurisdiction remain pending."}],
        borderline_excluded=[])
    relevance_ref = write(PROPOSALS / "relevance.json", relevance)
    batch_ref = write(PROPOSALS / "relevance_batch.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                           for name, kind, domain in PARAMETERS],
        "structure": {"activation": {"condition": "Vehicle operator enters a source-identified roundabout with another vehicle already circulating.",
                                     "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Yield right-of-way to vehicles already in the roundabout and wait for a traffic gap before entering.",
                           "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Join original entering-vehicle motion, circulating-vehicle route and occupancy, and observed pre-entry spacing in time.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase,
                "note": "No legal traffic-gap threshold is supplied; independent source and physical review required."}
                for phrase, _, _ in PHRASES]}}
    template_ref = write(PROPOSALS / "template.json", template)
    judgments = []
    for index, (phrase, name, unit) in enumerate(PHRASES, 1):
        item = {"name": name, "unit": unit,
                "description": "Source-bound original Native map, lane, body, speed and time observations."}
        judgments.append(write(PROPOSALS / f"judgment-{index}.json", {
            "status": "draft", "template_id": TEMPLATE, "phrase": phrase,
            "note": "Physical observation does not itself decide legal right-of-way or gap sufficiency.",
            "observable_requirements": {"observables": [item], "recording_needs": [item],
                "context_inputs": [{"name": "reviewed_roundabout_source", "unit": "source",
                    "description": "Original jurisdiction, map, connected entry and circulating route source."}],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": ["No numeric legal gap threshold in the frozen source."]}}))
    binding_ref = write(PROPOSALS / "bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C130864 multilane roundabout cell; original site pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": "C130864",
            "rationale": "Frozen catalog identity, not physical site evidence."}],
        variable_parameters=[{"name": name, "kind": kind, "range_or_domain": domain,
                              "used_by_laws": [LAW]} for name, kind, domain in PARAMETERS]))
    cases = []
    for case in plan["cases"]:
        values = {name: case[name] for name in
                  ("opponent_lane_relation", "planned_gap_condition", "ego_entry_request")}
        values["capture_profile"] = "four original RGB views, 20 Hz, 900 frames"
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe", "rationale": case["recording_description"],
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                                     for name, kind, _ in PARAMETERS},
            "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES],
            "recording_description": case["recording_description"],
            "probe": {"primary_variable": "ego_entry_request",
                "comparison_or_standard": "same reviewed map, lane, actors, 20 Hz and four-camera policy",
                "target_value_or_branch": case["ego_entry_request"]}})
    sweep = {"sweep_id": "source-gated-gap-coverage", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": "Physical and legal source review pending."}
                          for phrase, _, _ in PHRASES],
        "rationale": "Requested near and wider conditions are engineering probes, not legal gap cutoffs.",
        "status": "incomplete", "missing_inputs": ["reviewed original roundabout map and routes",
            "actual circulating-vehicle and entry trace", "source-supported legal gap assessment"]}
    write(PROPOSALS / "pending-source-judgment-sweep.json", sweep)
    cases_ref = write(PROPOSALS / "cases.json", dict(common, sweep_specs=[sweep],
        sweeps_expanded=True, sweep_expansion_scope="Six selected physical probes enumerated; source judgment incomplete.",
        cases=cases))
    write(PROPOSALS / "semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ROOT.name,
        "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgments,
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    build()
    print("source-gated roundabout semantic chain authored")
