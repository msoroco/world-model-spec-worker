"""Author the source-gated canonical NRS 484B.490 stage chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"
LAW = "NRS-484B-490"
CELL = "C412262"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
NOTE = ("Public highway dedication, boundaries and full width, erected official device "
        "authority, conformity and extent, and parking purpose require reviewed originals. "
        "No numeric legal narrowness cutoff is inferred.")
PARAMETERS = (
    ("highway_width_request", "world_setup", "reviewed full highway width profile; narrowness unresolved"),
    ("device_request", "world_setup", "erected official no-parking device, absence or extent"),
    ("parking_location_request", "controller", "body footprint upon or outside highway; approach direction"),
    ("activity_request", "controller", "park, stand, travel or temporary active loading"),
)
PHRASES = (
    ("official traffic-control devices are erected prohibiting parking", "official_device_and_extent"),
    ("a narrow highway", "full_highway_boundary_and_width"),
    ("park a vehicle upon any such highway", "responsible_person_and_activity"),
)


def write(name: str, value: dict) -> dict:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": CELL, "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low",
        "relevance_type": "source-reviewed motor vehicle parking on a narrow highway with official prohibitory device",
        "notes": NOTE}], borderline_excluded=[])
    batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                           for name, kind, domain in PARAMETERS],
        "structure": {"activation": {"condition": "Official traffic-control devices are erected prohibiting parking on a source-reviewed narrow highway.",
            "numeric_conditions": []},
            "obligation": {"type": "must_not", "description": "A person shall not park a vehicle upon such a highway when the official device condition is met.",
                "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Observe original device applicability and vehicle activity during the source-sealed 45 s trace.",
                "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": NOTE} for phrase, _ in PHRASES]}}
    template_ref = write("template.json", template)
    judgments = []
    for index, (phrase, name) in enumerate(PHRASES, 1):
        item = {"name": name, "unit": "structured",
            "description": "Source-bound original highway, device, vehicle body and activity observation."}
        judgments.append(write(f"judgment-{index}.json", {"status": "draft",
            "template_id": TEMPLATE, "phrase": phrase, "note": NOTE,
            "observable_requirements": {"observables": [item], "recording_needs": [item],
                "context_inputs": [{"name": "reviewed_original_highway_survey", "unit": "source",
                    "description": "Reviewed highway dedication, full width, device authority/content/conformity/extent and parking purpose."}],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": [NOTE]}}))
    binding_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C412262 paved-road parking-device cell; original highway and device authority pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": CELL,
            "rationale": "Frozen catalog identity, not original physical evidence."}],
        variable_parameters=[{"name": name, "kind": kind, "range_or_domain": domain,
            "used_by_laws": [LAW]} for name, kind, domain in PARAMETERS]))
    case_proposal = json.loads((OUT / "cases.json").read_text(encoding="utf-8"))
    selected = [row for row in case_proposal["cases"] if row["target_type"] != "baseline"]
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared source-gated highway and device context; original survey pending.",
        "variable_assignments": selected[0]["variable_assignments"],
        "unresolved_judgment_calls": [phrase for phrase, _ in PHRASES],
        "recording_description": selected[0]["recording_description"]}
    primary_by_case = {
        "park_narrow_device": "device_request",
        "stand_narrow_device": "activity_request",
        "loading_narrow_device": "activity_request",
        "travel_narrow_device": "activity_request",
        "park_narrow_no_device": "device_request",
        "park_narrow_unofficial_device": "device_request",
        "park_narrow_outside_extent": "device_request",
        "park_wider_device": "highway_width_request",
        "park_narrow_device_off_highway": "parking_location_request",
        "park_narrow_device_reverse_approach": "parking_location_request",
    }
    for row in selected:
        variant = row["case_id"].rsplit("__", 1)[-1]
        row["target_type"] = "boundary_probe"
        row["probe"] = {"primary_variable": primary_by_case[variant],
                        "comparison_or_standard": "source-gated park-narrow-device reference and one declared contrast",
                        "target_value_or_branch": variant}
    sweep = {"sweep_id": "source-gated-highway-device-and-parking", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": NOTE} for phrase, _ in PHRASES],
        "rationale": "Ten exact highway, device, location and activity contrasts preserve unresolved judgments.",
        "status": "incomplete", "missing_inputs": ["reviewed original public highway boundaries and full width",
            "official device erection, authority, conformity, content and extent",
            "original parking-purpose and activity review"]}
    case_proposal["sweep_specs"] = [sweep]
    case_proposal["sweeps_expanded"] = True
    case_proposal["cases"] = [baseline] + selected
    cases_ref = write("cases.json", case_proposal)
    write("semantic-index.json", {"format": "worker-semantic-delivery", "assignment_id": ROOT.name,
        "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgments,
                   "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    build()
    print("ten source-gated narrow-highway cases bound to semantic stage chain")
