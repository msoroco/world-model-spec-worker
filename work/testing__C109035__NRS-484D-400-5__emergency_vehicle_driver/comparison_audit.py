"""Independent fixed-condition checks for C109035 saved comparison records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from emergency_scene import CASE_KNOBS

PREFIX = "testing__C109035__NRS-484D-400-5__emergency_vehicle_driver__"


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


def compare_exact(plan_path: Path, comparison_id: str, records: list[dict]) -> dict:
    """Join a saved comparison to its exact frozen-plan membership and controls."""
    data = Path(plan_path).read_bytes()
    plan = json.loads(data)
    matches = [item for item in plan.get("comparisons", [])
               if item.get("comparison_id") == comparison_id]
    if len(matches) != 1:
        raise ValueError("Exact comparison absent or ambiguous in case plan")
    expected = matches[0]["case_ids"]
    if len(expected) != len(records) or set(expected) != {r.get("case_id") for r in records}:
        raise ValueError("Exact comparison case membership mismatch")
    for record in records:
        suffix = record["case_id"][len(PREFIX):] if record["case_id"].startswith(PREFIX) else ""
        if suffix not in CASE_KNOBS:
            raise ValueError("Unknown exact case")
        knobs = CASE_KNOBS[suffix]
        if (record.get("event_context") != knobs["event"]
                or type(record.get("requested_siren")) is not bool
                or type(record.get("requested_warning_lamps")) is not bool
                or record["requested_siren"] != knobs["siren"]
                or record["requested_warning_lamps"] != knobs["lamps"]):
            raise ValueError("Authored controls differ from exact case")
    result = compare(comparison_id, records)
    result["case_plan_sha256"] = hashlib.sha256(data).hexdigest()
    result["physical_status"] = "source_join_only"
    return result
