"""Measure independent school schedule and physical beacon facts without a legal verdict."""

from __future__ import annotations

from datetime import datetime, timedelta


HASH_FIELDS = (
    "calendar_source_sha256", "operation_schedule_source_sha256",
    "class_schedule_source_sha256", "local_clock_source_sha256",
    "beacon_configuration_source_sha256", "beacon_state_source_sha256",
    "sign_instruction_source_sha256", "zone_designation_source_sha256",
)


def instant(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("original offset-aware " + label + " required")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("valid " + label + " required") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("offset-aware " + label + " required")
    return dt


def derive(packet: dict) -> dict:
    if not isinstance(packet, dict) or packet.get("source_kind") != "original_school_schedule_and_device_readback":
        raise ValueError("original school schedule and device readback required")
    for name in HASH_FIELDS:
        value = packet.get(name)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("independent source hash required: " + name)
    now = instant(packet.get("local_datetime"), "local clock")
    end = instant(packet.get("last_operation_end"), "last operation end")
    start = instant(packet.get("next_operation_start"), "next operation start")
    class_start = instant(packet.get("class_start"), "class start")
    class_end = instant(packet.get("class_end"), "class end")
    if not end < start or not class_start < class_end:
        raise ValueError("school schedule ordering invalid")
    for name in ("school_in_session", "beacon_operational", "sign_limit_active",
                 "zone_designated_by_operational_beacon"):
        if type(packet.get(name)) is not bool:
            raise ValueError("original school/device fact required: " + name)
    count = packet.get("beacon_yellow_light_count")
    if type(count) is not int or count < 0:
        raise ValueError("original beacon yellow-light count required")
    if type(packet.get("beacon_alternating_flash_capable")) is not bool:
        raise ValueError("original beacon alternating capability required")
    if packet["zone_designated_by_operational_beacon"]:
        if not packet["beacon_operational"] or count < 2 or not packet["beacon_alternating_flash_capable"]:
            raise ValueError("operational speed-limit beacon definition not demonstrated")
    lights = packet.get("lamp_state_samples")
    if not isinstance(lights, list) or len(lights) < 4:
        raise ValueError("synchronized original lamp-state samples required")
    for row in lights:
        if not isinstance(row, dict) or type(row.get("original_frame")) is not int:
            raise ValueError("original lamp frame required")
        states = row.get("yellow_lamps_on")
        if not isinstance(states, list) or len(states) != count or any(type(state) is not bool for state in states):
            raise ValueError("all original yellow lamp states required")
    frames = [row["original_frame"] for row in lights]
    if frames != sorted(set(frames)):
        raise ValueError("lamp samples must retain unique original frame order")
    alternating_observed = any(
        left["yellow_lamps_on"][i] and right["yellow_lamps_on"][j]
        and not left["yellow_lamps_on"][j] and not right["yellow_lamps_on"][i]
        for left, right in zip(lights, lights[1:])
        for i in range(count) for j in range(count) if i != j
    )
    if alternating_observed and not packet["beacon_operational"]:
        raise ValueError("nonoperational beacon cannot have original alternating indication")
    after_end_min = (now - end).total_seconds() / 60
    before_start_min = (start - now).total_seconds() / 60
    # Equality is a measured boundary. Its legal treatment stays unresolved.
    between_operation = end + timedelta(minutes=30) < now < start - timedelta(minutes=30)
    boundary = now == end + timedelta(minutes=30) or now == start - timedelta(minutes=30)
    return {
        "school_in_session": packet["school_in_session"],
        "after_end_minutes": after_end_min,
        "before_start_minutes": before_start_min,
        "between_operation_interior": between_operation,
        "half_hour_boundary": boundary,
        "during_pupil_class_hours": class_start <= now <= class_end,
        "zone_designated_by_operational_beacon": packet["zone_designated_by_operational_beacon"],
        "beacon_operational": packet["beacon_operational"],
        "beacon_yellow_light_count": count,
        "alternating_flash_observed": alternating_observed,
        "sign_limit_active": packet["sign_limit_active"],
        "legal_judgment": None,
        "source_limit": "Source clock and device states are measurements; original zone governance and statutory exception need independent review.",
    }
