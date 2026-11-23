"""Independent fixed-condition checks for C109035 saved comparison records."""
from __future__ import annotations


FIXED = (
    "cell_id", "actor", "map_sha256", "site_sha256", "route_sha256",
    "pedestrian_plan_sha256", "equipment_record_sha256", "capture_profile_sha256",
    "weather_sha256", "ego_speed_policy_sha256",
)
DELIBERATE = {
    "response_device_choice": {"requested_siren", "requested_warning_lamps"},
    "qualifying_event_for_siren": {"event_context"},
    "lamps_without_siren": {"event_context"},
}


def compare(comparison_id: str, records: list[dict]) -> dict:
    if comparison_id not in DELIBERATE:
        raise ValueError("Unknown comparison")
    if len(records) < 2 or len({r.get("case_id") for r in records}) != len(records):
        raise ValueError("Comparison needs distinct exact cases")
    for field in FIXED:
        values = [r.get(field) for r in records]
        if any(v in (None, "") for v in values) or len(set(values)) != 1:
            raise ValueError("Fixed condition missing or changed: " + field)
    allowed = DELIBERATE[comparison_id]
    for field in ("requested_siren", "requested_warning_lamps", "event_context"):
        values = [r.get(field) for r in records]
        if any(v is None for v in values):
            raise ValueError("Comparison variable missing: " + field)
        if field not in allowed and len(set(values)) != 1:
            raise ValueError("Undeclared change: " + field)
    if not any(len({r[field] for r in records}) > 1 for field in allowed):
        raise ValueError("Declared comparison has no observed authored-variable difference")
    return {"comparison_id": comparison_id, "case_ids": [r["case_id"] for r in records],
            "fixed_fields_verified": list(FIXED), "deliberate_fields": sorted(allowed),
            "physical_status": "source_join_only"}
