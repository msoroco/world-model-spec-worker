"""Independent source-bound comparison of device instructions and exception."""
from __future__ import annotations


def audit(comparison: dict, left: dict, right: dict) -> dict:
    if [left.get("case_id"), right.get("case_id")] != comparison["case_ids"]:
        raise ValueError("comparison case identity mismatch")
    for row in (left, right):
        if row.get("source_kind") != "original_native" or row.get("legal_assessment") != "unresolved":
            raise ValueError("missing original measurement or legal separation")
        if not row.get("device_id") or not row.get("bike_id"):
            raise ValueError("missing participant or device identity")
        if "crossing_frame" not in row or "device_state_at_crossing" not in row or "officer_command_at_crossing" not in row:
            raise ValueError("incomplete crossing measurement")
        if not row.get("context") or not row.get("source_hashes"):
            raise ValueError("missing source-bound context")
    variable = comparison["deliberate_variable"]
    if variable not in {"operator_motion", "device_instruction", "officer_direction", "device_type"}:
        raise ValueError("unknown deliberate variable")
    fields = ("map_name", "jurisdiction_source", "governed_approach", "bike_blueprint_id", "route", "camera_contract", "duration_s", "device_authority_source", "vehicle_applicability_source", "device_type", "device_instruction", "officer_direction")
    for field in fields:
        if field == variable or (variable == "device_type" and field in {"device_authority_source", "vehicle_applicability_source", "device_instruction"}):
            continue
        if left["context"].get(field) != right["context"].get(field):
            raise ValueError("fixed condition changed: " + field)
    observed = {"operator_motion": "crossing_frame", "device_instruction": "device_state_at_crossing", "officer_direction": "officer_command_at_crossing", "device_type": "device_id"}[variable]
    if left.get(observed) == right.get(observed):
        raise ValueError("declared variable did not differ: " + variable)
    if left["source_hashes"].get("site") != right["source_hashes"].get("site") and variable != "device_type":
        raise ValueError("site source changed")
    return {"format": "c111329-device-comparison-audit", "comparison_id": comparison["comparison_id"], "case_ids": comparison["case_ids"], "passed": True, "legal_assessment": "unresolved"}
