"""Author source-gated exact NRS 484B.220(2) semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"
LAW, CELL, ACTOR = "NRS-484B-220-2", "C130282", "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PHRASES = (
    ("rotary traffic island", "reviewed_island_source", "source"),
    ("passing around", "observed_lane", "structured"),
    ("only to the right of such island", "island_side_and_overlap", "structured"),
)
PARAMETERS = (
    ("circulation_lane_role", "world_setup", "inner or outer reviewed connected circulation lane"),
    ("requested_island_side", "controller", "right or left engineering route request"),
    ("capture_profile", "world_setup", "four original RGB views, 20 Hz, 900 frames"),
)
NOTE = "Original rotary-island identity, physical polygon, connected route, driver and continuous passage require independent source and physical review."


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": CELL, "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low",
        "relevance_type": "motor vehicle passage to right of a qualifying rotary traffic island",
        "notes": NOTE}], borderline_excluded=[])
    relevance_batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                           for name, kind, domain in PARAMETERS],
        "structure": {"activation": {"condition": "A vehicle passes around a source-identified rotary traffic island.",
            "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Drive only to the right of the rotary traffic island while passing around it.",
                           "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Use original ordered passage, body, heading and island geometry throughout the observed interval.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": NOTE} for phrase, _, _ in PHRASES]}}
    template_ref = write("template.json", template)
    judgments = []
    for index, (phrase, name, unit) in enumerate(PHRASES, 1):
        observable = {"name": name, "unit": unit,
                      "description": "Source-bound original rotary-island map, lane, body, heading and camera observations."}
        judgments.append(write(f"judgment-{index}.json", {"status": "draft",
            "template_id": TEMPLATE, "phrase": phrase, "note": NOTE,
            "observable_requirements": {"observables": [observable], "recording_needs": [observable],
                "context_inputs": [{"name": "reviewed_island_source", "unit": "source",
                    "description": "Independently reviewed original physical island identity, polygon and connected routes."}],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": ["Sampled local side does not establish continuous legal judgment."]}}))
    binding_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C130282 rotary traffic island cell; original island source pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": CELL,
                           "rationale": "Frozen catalog identity, not original island evidence."}],
        variable_parameters=[{"name": name, "kind": kind, "range_or_domain": domain,
                              "used_by_laws": [LAW]} for name, kind, domain in PARAMETERS]))
    first = json.loads((ROOT / "construction.json").read_text(encoding="utf-8"))["recording_description"]
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared reviewed island passage reference pending original source.",
        "variable_assignments": {name: {"kind": kind, "value": value}
            for (name, kind, _), value in zip(PARAMETERS,
                ("inner", "right", "four original RGB views, 20 Hz, 900 frames"))},
        "recording_description": first,
        "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES]}
    cases = [baseline]
    for case in plan["cases"]:
        cid = case["case_id"]
        tag = cid.split("__")[-1]
        lane, side = tag.split("_")
        path = ROOT / "construction.json" if cid.endswith("__inner_right") else ROOT / "cases" / tag / "construction.json"
        description = json.loads(path.read_text(encoding="utf-8"))["recording_description"]
        values = {"circulation_lane_role": lane, "requested_island_side": side,
                  "capture_profile": "four original RGB views, 20 Hz, 900 frames"}
        cases.append({"case_id": cid, "target_law_id": LAW, "target_type": "boundary_probe",
            "rationale": case["recording_description"], "paired_probe_id": "source-gated-island-side-and-lane",
            "deliberate_differences": ["circulation_lane_role", "requested_island_side"],
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                for name, kind, _ in PARAMETERS},
            "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES],
            "recording_description": description,
            "probe": {"primary_variable": "requested_island_side",
                "comparison_or_standard": "same reviewed island, motor vehicle, route source, 20 Hz and four-camera policy",
                "target_value_or_branch": side}})
    sweep = {"sweep_id": "source-gated-island-coverage", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": NOTE} for phrase, _, _ in PHRASES],
        "rationale": "Exact lane and side requests are engineering probes, not a legal side determination.",
        "status": "incomplete", "missing_inputs": ["reviewed original rotary-island identity and polygon",
            "connected inner/outer routes including physically reviewed left-side contrast",
            "actual original vehicle trace and continuous legal passage review"]}
    write("pending-source-judgment-sweep.json", sweep)
    cases_ref = write("cases.json", dict(common, sweep_specs=[sweep],
        sweeps_expanded=True, sweep_expansion_scope="Four selected source-gated engineering probes enumerated; original judgment incomplete.",
        cases=cases))
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ROOT.name,
        "stages": {"relevance_batch": relevance_batch_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgments,
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    build()
    print("four source-gated island semantic cases authored")
