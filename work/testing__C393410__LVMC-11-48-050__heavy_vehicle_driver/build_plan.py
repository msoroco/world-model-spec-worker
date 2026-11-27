"""Construct the exact 11.48.050 source-gated comparison plan."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
ASSIGNMENT_SOURCE = f"inputs/{AID}/assignment.json"

# Values are engineering targets for prospective recordings. Actual unladen
# weight, civil time, district classification and permit validity require
# independent original sources at capture and review.
CASES = {
    "night_nonroute_no_permit": (8001, "20:00", "residence", "non_truck", "none"),
    "night_nonroute_valid_permit": (8001, "20:00", "residence", "non_truck", "valid"),
    "night_nonroute_application_only": (8001, "20:00", "residence", "non_truck", "application_only"),
    "night_nonroute_route_condition_breach": (8001, "20:00", "residence", "non_truck", "route_condition_breach"),
    "night_nonroute_time_condition_breach": (8001, "20:00", "residence", "non_truck", "time_condition_breach"),
    "night_truck_route": (8001, "20:00", "residence", "truck_route", "none"),
    "night_nonresidence": (8001, "20:00", "nonresidence", "non_truck", "none"),
    "day_nonroute": (8001, "18:59", "residence", "non_truck", "none"),
    "weight_below_8000": (7999, "20:00", "residence", "non_truck", "none"),
    "weight_at_8000": (8000, "20:00", "residence", "non_truck", "none"),
    "time_at_1900": (8001, "19:00", "residence", "non_truck", "none"),
    "time_before_0600": (8001, "05:59", "residence", "non_truck", "none"),
    "time_at_0600": (8001, "06:00", "residence", "non_truck", "none"),
}


def case_id(short: str) -> str:
    return AID + "__" + short


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    plan["planning_status"] = "exact_source_gated_cases_selected"
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": name, "interval": "all 900 original 20 Hz frames", "subject": subject}
            for name, subject in (
                ("overview", "residence frontage, travel street and truck-route boundary"),
                ("approach", "ego vehicle and original street identity"),
                ("reference_corner", "district frontage and route designation context"),
                ("driver_reference", "ego operation, vehicle identity and endpoint"))]}
    plan["evidence_review"]["gaps"] = [{
        "id": "unverified-night-restriction-sources",
        "requirement": "Original vehicle unladen weight, local civil time, municipal residence district, truck-route designation and written permit conditions",
        "source": ASSIGNMENT_SOURCE,
        "why_existing_insufficient": "Frozen evidence inventory lists zero accepted recordings."}]
    plan["cases"] = []
    for short, (weight, time, district, route, permit) in CASES.items():
        plan["cases"].append({
            "case_id": case_id(short), "target_law_id": plan["law_id"],
            "kind": "delivery", "branch": plan["selected_branches"][0]["branch"],
            "new_capture_selected": True, "physical_acceptance_claimed": False,
            "construction_status": "selected_source_deferred",
            "construction": f"cases/{short}/construction.json",
            "measurement_contract": f"cases/{short}/measurement-contract.json",
            "gap_ids": ["unverified-night-restriction-sources"],
            "target_unladen_lb": weight, "target_local_time": time,
            "target_district": district, "target_street_class": route,
            "target_permit_status": permit, "legal_judgment": "unresolved",
            "physical_risk_assessment": {"status": "physical",
                "risk": "Original heavy vehicle may not complete reviewed street segment and remain in all four views",
                "trigger": "missing original motion completion or actual camera pixels",
                "fallback_change": "lower target speed on the same reviewed route, vehicle and source conditions"}})
    baseline = case_id("night_nonroute_no_permit")
    comparisons = [
        ("written_permit_vs_none", "night_nonroute_valid_permit", "written permit with matching applicant, vehicle, route, time and conditions"),
        ("application_only_vs_none", "night_nonroute_application_only", "written application without issued written permit"),
        ("route_condition_vs_valid", "night_nonroute_route_condition_breach", "written permit route condition breached", "night_nonroute_valid_permit"),
        ("time_condition_vs_valid", "night_nonroute_time_condition_breach", "written permit time condition breached", "night_nonroute_valid_permit"),
        ("truck_route_vs_nonroute", "night_truck_route", "authoritatively designated truck route rather than non-truck street"),
        ("residence_vs_other", "night_nonresidence", "source-reviewed nonresidence district rather than residence district"),
        ("before_1900_vs_night", "day_nonroute", "local civil time 18:59 rather than 20:00"),
        ("weight_below_vs_above", "weight_below_8000", "vehicle-specific unladen weight 7,999 lb rather than 8,001 lb"),
        ("weight_at_vs_above", "weight_at_8000", "vehicle-specific unladen weight 8,000 lb rather than 8,001 lb"),
        ("time_1900_vs_inside", "time_at_1900", "local civil time 19:00 rather than 20:00"),
        ("time_before_0600_vs_inside", "time_before_0600", "local civil time 05:59 rather than 20:00"),
        ("time_0600_vs_inside", "time_at_0600", "local civil time 06:00 rather than 20:00"),
    ]
    plan["comparisons"] = []
    for comparison in comparisons:
        name, variant, difference, *reference = comparison
        ref = reference[0] if reference else "night_nonroute_no_permit"
        plan["comparisons"].append({
            "comparison_id": name, "case_ids": [case_id(variant), case_id(ref)],
            "fixed_conditions": ["same C393410 road network, actor, 45 s duration, 20 Hz four cameras and selected vehicle except declared variation"],
            "deliberate_differences": [difference],
            "status": "planned_cpu_construction"})
    observations = [
        ("ego_operation", "original 20 Hz ego identity, motion and street history"),
        ("actual_unladen_weight", "vehicle-specific original documentary unladen weight, not visual class"),
        ("local_civil_time", "timezone-qualified original local civil clock and DST status"),
        ("residence_district", "municipal district and frontage/business exclusion source review"),
        ("street_designation", "authoritative truck-route extent and traveled street identity"),
        ("written_permit", "issued written DPW permit, applicant, vehicle, route, time and every condition")]
    plan["observations"] = [{"name": name, "mandatory": True, "method": method,
        "source": "reviewed-night-restriction.json" if name != "ego_operation" else "original-operation.json"}
        for name, method in observations]
    requirements = [
        ("vehicle in excess of eight thousand pounds unladen", ["night_nonroute_no_permit", "weight_below_8000", "weight_at_8000"]),
        ("operated or moved upon street", ["night_nonroute_no_permit", "night_truck_route"]),
        ("street other than truck route", ["night_nonroute_no_permit", "night_truck_route"]),
        ("residence district", ["night_nonroute_no_permit", "night_nonresidence"]),
        ("between seven p.m. and six a.m. local civil time", ["day_nonroute", "time_at_1900", "night_nonroute_no_permit", "time_before_0600", "time_at_0600"]),
        ("written application and issued written DPW permit", ["night_nonroute_no_permit", "night_nonroute_application_only", "night_nonroute_valid_permit"]),
        ("authorized applicant and vehicle", ["night_nonroute_valid_permit", "night_nonroute_no_permit"]),
        ("permit route, time and other conditions", ["night_nonroute_valid_permit", "night_nonroute_route_condition_breach", "night_nonroute_time_condition_breach"]),
    ]
    plan["requirement_dispositions"] = [{"requirement": requirement,
        "source": ASSIGNMENT_SOURCE, "status": "selected_required",
        "evidence_or_gap": "No accepted recording; original reviewed source and operation are required.",
        "case_ids": [case_id(short) for short in shorts]}
        for requirement, shorts in requirements]
    plan["source_observation_mapping"] = {}
    plan["runtime_uncertainties"] = [
        "Original municipal route designation, residence frontage/business exclusion, local civil time, vehicle-specific unladen weight and permit records require operator-reviewed sources.",
        "Actual Native heavy-vehicle motion and four camera pixel coverage require later physical delivery.",
        "The statute supplies an exact >8,000 lb threshold; whether its time endpoints are included and whether permit conditions authorize the operation remain legal judgments, not worker verdicts."]
    (HERE / "case-plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


if __name__ == "__main__":
    print(len(build()["cases"]), "source-gated cases planned")
