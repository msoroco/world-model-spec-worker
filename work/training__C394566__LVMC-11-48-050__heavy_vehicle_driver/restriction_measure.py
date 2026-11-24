"""Source-hashed factual measurements for LVMC 11.48.050.

This evaluates the observed prerequisites separately. It does not establish that
an administrative document is authentic or return a legal verdict.
"""
from __future__ import annotations

from datetime import datetime, time
import hashlib
import json
import math
from zoneinfo import ZoneInfo


def night_status(instant: datetime) -> str:
    local = instant.astimezone(ZoneInfo("America/Los_Angeles"))
    clock = local.time().replace(tzinfo=None)
    if clock in (time(19), time(6)):
        return "endpoint_unresolved"
    return "inside" if clock > time(19) or clock < time(6) else "outside"


def measure(source: bytes, expected_sha256: str) -> dict:
    digest = hashlib.sha256(source).hexdigest()
    if digest != expected_sha256:
        raise ValueError("source packet hash mismatch")
    facts = json.loads(source)
    if facts.get("source_kind") not in ("synthetic_native_sample", "original_review_packet"):
        raise ValueError("source kind missing")
    weight = facts.get("unladen_weight_lb")
    if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0:
        raise ValueError("vehicle-specific unladen weight source missing")
    if not isinstance(facts.get("weight_source_ref"), str) or not facts["weight_source_ref"]:
        raise ValueError("unladen weight provenance missing")
    if facts.get("district") not in ("residence", "other", "unverified"):
        raise ValueError("district classification source missing")
    if facts.get("truck_route") not in (True, False, None):
        raise ValueError("truck-route designation source missing")
    if not isinstance(facts.get("route_source_ref"), str) or not facts["route_source_ref"]:
        raise ValueError("truck-route authority provenance missing")
    stamp = facts.get("civil_timestamp")
    if not isinstance(stamp, str):
        raise ValueError("local civil time source missing")
    try:
        instant = datetime.fromisoformat(stamp)
    except ValueError as error:
        raise ValueError("invalid local civil timestamp") from error
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("civil time requires UTC offset")
    speed = facts.get("observed_speed_mps")
    if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
        raise ValueError("original movement source missing")
    if facts.get("written_permit_status") not in ("absent", "present", "unverified"):
        raise ValueError("written permit status source missing")
    return {"format": "c394566-restriction-facts-v1", "source_sha256": digest,
            "vehicle_over_8000_lb": weight > 8000,
            "night_window": night_status(instant),
            "residence_district": None if facts["district"] == "unverified" else facts["district"] == "residence",
            "non_truck_route": None if facts["truck_route"] is None else not facts["truck_route"],
            "observed_movement": speed > 0,
            "written_permit_status": facts["written_permit_status"],
            "permit_scope_and_conditions_verified": False,
            "legal_result": None,
            "limitations": ["clock endpoints preserved as unresolved",
                            "route, district, weight, and permit documents require original independent review",
                            "written permit identity, routes, times and conditions are not decided here"]}
