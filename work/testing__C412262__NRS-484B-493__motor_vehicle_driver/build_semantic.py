"""Author the source-gated canonical NRS 484B.493 stage chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "proposals"
LAW = "NRS-484B-493"
CELL = "C412262"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
NOTE = ("Street direction, official notice erection and extent, the statutory left side, "
        "and stopping purpose require reviewed originals. No legal side or time cutoff is inferred.")
PARAMETERS = (
    ("street_direction_request", "world_setup", "reviewed one-way or two-way street order and geometry"),
    ("notice_request", "world_setup", "official notice erection, applicability and extent from reviewed sources"),
    ("vehicle_side_request", "controller", "left or right side relative to permitted direction"),
    ("activity_request", "controller", "park, stand, travel or temporary halt purpose"),
)
PHRASES = (
    ("official traffic-control devices are erected giving notice thereof", "one_way_street_and_notice"),
    ("left-hand side of a one-way street", "vehicle_center_and_body"),
    ("stand or park a vehicle", "responsible_person_and_halt_purpose"),
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
        "relevance_type": "source-reviewed motor vehicle standing or parking beside a one-way street",
        "notes": NOTE}], borderline_excluded=[])
    batch_ref = write("relevance_batch.json", relevance)
    relevance_ref = write("relevance.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": kind, "range_or_domain": domain}
                           for name, kind, domain in PARAMETERS],
        "structure": {"activation": {"condition": "Official traffic-control devices are erected giving notice on a source-reviewed one-way street.",
            "numeric_conditions": []},
            "obligation": {"type": "must_not", "description": "A person shall not stand or park a vehicle upon the left-hand side of that one-way street when the notice condition is met.",
                "numeric_conditions": []},
            "exceptions": [],
            "timing": {"description": "Observe original notice applicability and vehicle activity during the source-sealed 45 s trace.",
                "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": NOTE} for phrase, _ in PHRASES]}}
    template_ref = write("template.json", template)
    judgments = []
    for index, (phrase, name) in enumerate(PHRASES, 1):
        item = {"name": name, "unit": "structured",
            "description": "Source-bound original street, notice, vehicle body and activity observation."}
        judgments.append(write(f"judgment-{index}.json", {"status": "draft",
            "template_id": TEMPLATE, "phrase": phrase, "note": NOTE,
            "observable_requirements": {"observables": [item], "recording_needs": [item],
                "context_inputs": [{"name": "reviewed_original_street_survey", "unit": "source",
                    "description": "Reviewed street order, official device authority/content/extent and halt purpose."}],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": [NOTE]}}))
    binding_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C412262 paved-road parking-device cell; original street and device authority pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": CELL,
            "rationale": "Frozen catalog identity, not original physical evidence."}],
        variable_parameters=[{"name": name, "kind": kind, "range_or_domain": domain,
            "used_by_laws": [LAW]} for name, kind, domain in PARAMETERS]))
    case_proposal = json.loads((OUT / "cases.json").read_text(encoding="utf-8"))
    selected = [row for row in case_proposal["cases"] if row["target_type"] != "baseline"]
    baseline = {"case_id": ROOT.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared source-gated street and notice context; original survey pending.",
        "variable_assignments": selected[0]["variable_assignments"],
        "unresolved_judgment_calls": [phrase for phrase, _ in PHRASES],
        "recording_description": selected[0]["recording_description"]}
    primary_by_case = {
        "park_left_notice": "vehicle_side_request",
        "stand_left_notice": "activity_request",
        "park_right_notice": "vehicle_side_request",
        "park_left_no_notice": "notice_request",
        "park_left_outside_notice_extent": "notice_request",
        "park_left_two_way": "street_direction_request",
        "travel_left_notice": "activity_request",
        "temporary_halt_left_notice": "activity_request",
        "park_left_notice_reverse_geometry": "street_direction_request",
    }
    for row in selected:
        variant = row["case_id"].rsplit("__", 1)[-1]
        row["target_type"] = "boundary_probe"
        row["probe"] = {"primary_variable": primary_by_case[variant],
                        "comparison_or_standard": "source-gated park-left-notice reference and one declared contrast",
                        "target_value_or_branch": variant}
    sweep = {"sweep_id": "source-gated-one-way-notice-and-side", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": NOTE} for phrase, _ in PHRASES],
        "rationale": "Nine exact street, notice, side and activity contrasts preserve unresolved judgments.",
        "status": "incomplete", "missing_inputs": ["reviewed original one-way street order and boundaries",
            "official notice erection, authority, content and extent",
            "original vehicle-side and activity-purpose review"]}
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
    print("nine source-gated one-way street cases bound to semantic stage chain")
