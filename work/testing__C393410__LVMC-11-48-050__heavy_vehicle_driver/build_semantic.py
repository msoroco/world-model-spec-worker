"""Author exact source-gated semantic proposals for LVMC 11.48.050."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "proposals"
LAW = "LVMC-11-48-050"
ACTOR = "heavy_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
NOTE = "Vehicle-specific unladen weight, local civil time, residence frontage/business exclusion, truck-route extents and written DPW permit scope/conditions require independent original-source review. No worker legal verdict."
VARIABLES = (
    ("target_unladen_lb", "vehicle-specific unladen weight targets 7,999, 8,000 and 8,001 lb"),
    ("target_local_time", "18:59, 19:00, 20:00, 05:59 and 06:00 local civil time"),
    ("target_district", "residence or nonresidence with original frontage sources"),
    ("target_street_class", "non-truck street or designated truck route"),
    ("target_permit_status", "none, application only, issued matching written permit, route/time condition breach"))


def write(name: str, value: object) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": "C393410", "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low", "relevance_type": "specific_match",
        "notes": NOTE}], borderline_excluded=[])
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    template = {"status": "draft", "law_id": LAW, "actor": ACTOR,
        "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": "world_setup",
            "range_or_domain": domain} for name, domain in VARIABLES],
        "structure": {"activation": {"condition": "Vehicle-specific actual unladen weight exceeds 8,000 lb; original ego operates or moves on a municipal residence-district street other than a truck route during the 7 p.m.–6 a.m. civil-time window.",
            "numeric_conditions": [{"name": "unladen_weight_boundary", "value": 8000,
                "unit": "lb", "operator": "greater_than", "variable": "actual_unladen_weight_lb"}]},
            "obligation": {"type": "must_not", "description": quote,
                "numeric_conditions": []},
            "exceptions": [{"source_clause": "special permit in writing",
                "description": "DPW may issue a written special permit upon written application; applicant, vehicle, authorized route/time and all conditions need original review.",
                "numeric_conditions": []}],
            "timing": {"description": "Join original UTC start and 20 Hz operation to source-reviewed local timezone; stage 18:59/19:00, 05:59/06:00 endpoints without deciding legal inclusivity.",
                "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": phrase, "note": NOTE}
                for phrase in ("residence district", "truck route", "between seven p.m. and six a.m.",
                               "written permit authorization and conditions")]}}
    template_ref = write("template.json", template)
    judgments = []
    channels = [
        ("ego_operation", "state", "Original 20 Hz ego motion and road identity."),
        ("actual_unladen_weight", "lb", "Vehicle-specific original documentary unladen weight."),
        ("local_civil_time", "local civil time", "UTC clock, timezone and uncertainty source."),
        ("residence_district", "source", "Original municipal frontage/business exclusion review."),
        ("street_designation", "source", "Authoritative truck-route extent and traveled street."),
        ("written_permit", "source", "Written application/issued permit, scope and conditions.")]
    for phrase in ("residence district", "truck route", "between seven p.m. and six a.m.",
                   "written permit authorization and conditions"):
        judgments.append(write("judgment-" + str(len(judgments) + 1) + ".json", {
            "status": "draft", "template_id": TEMPLATE, "phrase": phrase, "note": NOTE,
            "observable_requirements": {"observables": [{"name": name, "unit": unit,
                "description": description} for name, unit, description in channels],
                "context_inputs": [{"name": "reviewed_night_truck_site", "unit": "source",
                    "description": "SHA-bound municipal, vehicle, clock and DPW administrative context."}],
                "recording_needs": [{"name": name, "unit": unit,
                    "description": description} for name, unit, description in channels],
                "sweep_dimensions": [], "landmarks": [],
                "limitations": ["Original sources, Native physical completion and legal interpretation remain independent review tasks."]}}))
    bindings_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}], context_refs=[],
        established_contexts=["Frozen C393410 residence-district travel cell; actual district, street, weight, time and permit need original sources."],
        fixed_parameters=[{"name": "assigned_cell", "value": "C393410",
            "rationale": "Frozen catalog identity, not original physical proof."}],
        variable_parameters=[{"name": name, "kind": "world_setup",
            "range_or_domain": domain, "used_by_laws": [LAW]} for name, domain in VARIABLES]))
    baseline = json.loads((HERE / "cases/night_nonroute_no_permit/construction.json").read_text())["recording_description"]
    cases = [{"case_id": HERE.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared source-reviewed original night-truck site reference.",
        "variable_assignments": {name: {"kind": "world_setup", "value": value}
            for name, value in (("target_unladen_lb", 8001), ("target_local_time", "20:00"),
                ("target_district", "residence"), ("target_street_class", "non_truck"),
                ("target_permit_status", "none"))},
        "recording_description": baseline,
        "unresolved_judgment_calls": ["residence district", "truck route",
            "between seven p.m. and six a.m.", "written permit authorization and conditions"]}]
    for case in plan["cases"]:
        short = case["case_id"].split("__")[-1]
        construction = json.loads((HERE / "cases" / short / "construction.json").read_text())
        values = {name: case[name] for name, _ in VARIABLES}
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "judgment_sweep",
            "rationale": "Controlled weight/time/street/district/written-permit source-gated branch probes.",
            "variable_assignments": {name: {"kind": "world_setup", "value": value}
                for name, value in values.items()},
            "paired_probe_id": "source-gated-night-truck-restriction",
            "deliberate_differences": list(values),
            "unresolved_judgment_calls": ["residence district", "truck route",
                "between seven p.m. and six a.m.", "written permit authorization and conditions"],
            "recording_description": construction["recording_description"],
            "probe": {"primary_variable": "target_permit_status",
                "comparison_or_standard": "same original reviewed site and vehicle except declared comparison variable",
                "target_value_or_branch": values}})
    sweep = {"sweep_id": "source-gated-night-truck-restriction", "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": NOTE} for phrase in (
            "residence district", "truck route", "between seven p.m. and six a.m.",
            "written permit authorization and conditions")],
        "status": "incomplete",
        "rationale": "Original municipal, vehicle, time and DPW administrative records are source judgments; no extra legal cutoff is invented.",
        "missing_inputs": ["authoritative residence frontage/business exclusion and truck-route extents",
            "vehicle-specific actual unladen weight", "timezone-qualified local civil clock",
            "written application, issued permit and all scope/conditions or reviewed administrative negative search"]}
    write("pending-source-judgment-sweep.json", sweep)
    cases_ref = write("cases.json", dict(common, cases=cases, sweep_specs=[sweep],
        sweeps_expanded=True,
        sweep_expansion_scope="Thirteen controlled original-source night restriction probes; legal judgment unresolved."))
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
        "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
            "template": template_ref, "judgment_observables": judgments,
            "bindings": bindings_ref, "cases": cases_ref}}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    build()
    print("thirteen exact night-truck semantic proposals authored")
