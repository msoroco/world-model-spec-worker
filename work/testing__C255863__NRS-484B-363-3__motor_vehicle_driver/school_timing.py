"""Source-bound clock and beacon facts for the school-zone U-turn exceptions."""

from __future__ import annotations

from datetime import datetime, timedelta


def _instant(value, name):
    if not isinstance(value, str):
        raise ValueError("source-bound " + name + " timestamp required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("valid " + name + " timestamp required") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("offset-aware " + name + " timestamp required")
    return parsed


def derive(packet: dict) -> dict:
    if not isinstance(packet, dict) or packet.get("source_kind") != "original_school_schedule_and_device_readback":
        raise ValueError("original school schedule and device readback required")
    required_hashes = ("calendar_source_sha256", "operation_schedule_source_sha256",
                       "class_schedule_source_sha256", "local_clock_source_sha256",
                       "beacon_configuration_source_sha256", "beacon_state_source_sha256",
                       "sign_instruction_source_sha256")
    for name in required_hashes:
        value = packet.get(name)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("independent source hash required: " + name)
    now = _instant(packet.get("local_datetime"), "local clock")
    end = _instant(packet.get("last_operation_end"), "last operation end")
    next_start = _instant(packet.get("next_operation_start"), "next operation start")
    class_start = _instant(packet.get("class_start"), "class start")
    class_end = _instant(packet.get("class_end"), "class end")
    if not end < next_start or not class_start < class_end:
        raise ValueError("source schedule ordering invalid")
    for name in ("school_in_session", "beacon_operational", "beacon_flashing",
                 "sign_limit_active"):
        if not isinstance(packet.get(name), bool):
            raise ValueError("original school/device state required: " + name)
    lights = packet.get("beacon_yellow_light_count")
    if type(lights) is not int or lights < 0:
        raise ValueError("original beacon light count required")
    alternating = packet.get("beacon_alternating_flash_capable")
    if not isinstance(alternating, bool):
        raise ValueError("original alternating flash capability required")
    if packet["beacon_operational"] and (lights < 2 or not alternating):
        raise ValueError("operational speed limit beacon definition not demonstrated")
    if packet["beacon_flashing"] and not packet["beacon_operational"]:
        raise ValueError("nonoperational beacon cannot be recorded flashing")
    outside_half_hour = end + timedelta(minutes=30) <= now <= next_start - timedelta(minutes=30)
    return {"school_session": packet["school_in_session"],
            "operation_window": not outside_half_hour,
            "outside_half_hour": outside_half_hour,
            "during_class": class_start <= now <= class_end,
            "beacon_operational": packet["beacon_operational"],
            "beacon_flashing": packet["beacon_flashing"],
            "sign_limit_active": packet["sign_limit_active"],
            "source_limit": "Clock arithmetic and device facts do not resolve undefined legal boundary treatment or U-turn legality."}
