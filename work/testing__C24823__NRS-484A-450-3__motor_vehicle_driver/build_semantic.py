"""Author exact source-gated NRS 484A.450(3) semantic proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"
LAW, CELL, ACTOR = "NRS-484A-450-3", "C24823", "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PHRASES = (
    ("if required for safety to stop", "reviewed_yield_context", "source"),
    ("crosswalk on the nearest side", "original_view_geometry", "structured"),
    ("clearly marked stop line", "yield_control_readback", "structured"),
    ("point nearest the intersecting highway where the driver has a view of approaching traffic", "original_view_geometry", "structured"),
)
PARAMETERS = (
    ("crosswalk_presence", "world_setup", "nearest crosswalk present or absent in reviewed original inventory"),
    ("marked_stop_line_presence", "world_setup", "clearly marked line present or absent in reviewed original inventory"),
    ("requested_stop_behavior", "controller", "exact source-selected reference, earlier obscured contrast or no-stop context"),
    ("safety_necessity_context", "world_setup", "independently sourced yes or no; unresolved until review"),
    ("capture_profile", "world_setup", "four original RGB views, 20 Hz, 900 frames"),
)
NOTE = "Original yield governance, safety necessity, crossing/line inventory, driver view and stop position require independent source and physical review; no legal numeric cutoff is inferred."


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
        "relevance_type": "motor vehicle approaching a source-identified yield sign and conditional stopping reference",
        "notes": NOTE}], borderline_excluded=[])
    relevance_batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                           for name, kind, domain in PARAMETERS],
        "structure": {"activation": {"condition": "Driver of a vehicle approaches a source-identified yield sign; independent safety review decides whether a stop is required.",
            "numeric_conditions": []},
            "obligation": {"type": "must", "description": "If stopping is required for safety, stop before the nearest-side crosswalk; if none, at a clearly marked stop line; if none, at the nearest point to the intersecting highway where the driver has a view of approaching traffic.",
                "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Use original ordered approach, stopping and intersection-entry samples with the reviewed reference hierarchy.",
                "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": NOTE} for phrase, _, _ in PHRASES]}}
    template_ref = write("template.json", template)
    judgments = []
    for index, (phrase, name, unit) in enumerate(PHRASES, 1):
        observable = {"name": name, "unit": unit,
            "description": "Source-bound original yield sign, safety, crossing/line hierarchy and vehicle/camera observations."}
        judgments.append(write(f"judgment-{index}.json", {"status": "draft",
            "template_id": TEMPLATE, "phrase": phrase, "note": NOTE,
            "observable_requirements": {"observables": [observable], "recording_needs": [observable],
                "context_inputs": [{"name": "reviewed_yield_context", "unit": "source",
                    "description": "Independently reviewed original safety necessity, sight and crossing/line inventory."}],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": ["Geometric ray, 0.1 m/s stop sample and controller target are engineering observations only."]}}))
    binding_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C24823 blind intersection and yield-sign cell; original governance and sight source pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": CELL,
            "rationale": "Frozen catalog identity, not original physical evidence."}],
        variable_parameters=[{"name": name, "kind": kind, "range_or_domain": domain,
            "used_by_laws": [LAW]} for name, kind, domain in PARAMETERS]))
    first = json.loads((ROOT / "construction.json").read_text(encoding="utf-8"))["recording_description"]
    baseline_values = ("absent", "absent", "fallback_nearest_view_stop", "yes", "four original RGB views, 20 Hz, 900 frames")
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared source-reviewed yield approach pending original site and safety review.",
        "variable_assignments": {name: {"kind": kind, "value": value}
            for (name, kind, _), value in zip(PARAMETERS, baseline_values)},
        "recording_description": first,
        "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES]}
    cases = [baseline]
    for index, case in enumerate(plan["cases"]):
        cid, tag = case["case_id"], case["variant"]
        path = ROOT / "construction.json" if index == 0 else ROOT / "cases" / tag / "construction.json"
        description = json.loads(path.read_text(encoding="utf-8"))["recording_description"]
        values = {"crosswalk_presence": case["crosswalk_status"],
                  "marked_stop_line_presence": case["marked_stop_line_status"],
                  "requested_stop_behavior": tag,
                  "safety_necessity_context": case["stopping_required_for_safety_context"],
                  "capture_profile": "four original RGB views, 20 Hz, 900 frames"}
        cases.append({"case_id": cid, "target_law_id": LAW, "target_type": "boundary_probe",
            "rationale": case["measurement"], "paired_probe_id": "source-gated-yield-reference-hierarchy",
            "deliberate_differences": ["crosswalk_presence", "marked_stop_line_presence",
                "requested_stop_behavior", "safety_necessity_context"],
            "variable_assignments": {name: {"kind": kind, "value": values[name]}
                for name, kind, _ in PARAMETERS},
            "unresolved_judgment_calls": [phrase for phrase, _, _ in PHRASES],
            "recording_description": description,
            "probe": {"primary_variable": "requested_stop_behavior",
                "comparison_or_standard": "same source-reviewed yield approach, motor driver, 20 Hz and four-camera policy",
                "target_value_or_branch": tag}})
    sweep = {"sweep_id": "source-gated-yield-reference-hierarchy", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": NOTE} for phrase, _, _ in PHRASES],
        "rationale": "Five exact hierarchy/safety contrasts are engineering probes, not legal sight or safety cutoffs.",
        "status": "incomplete", "missing_inputs": ["reviewed original yield sign and crossing/line inventory",
            "original occluder and driver-viewpoint sight with approaching traffic",
            "independent safety necessity and physical stop trace review"]}
    write("pending-source-judgment-sweep.json", sweep)
    cases_ref = write("cases.json", dict(common, sweep_specs=[sweep],
        sweeps_expanded=True,
        sweep_expansion_scope="Five selected source-gated hierarchy and safety probes enumerated; original judgments pending.",
        cases=cases))
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ROOT.name,
        "stages": {"relevance_batch": relevance_batch_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgments,
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    build()
    print("five exact source-gated yield semantic cases authored")
