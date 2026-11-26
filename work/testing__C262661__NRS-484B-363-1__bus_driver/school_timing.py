"""Derive school calendar and device branches from independently sealed facts."""

from datetime import datetime, timedelta

HASH_FIELDS = {
    "calendar_source_sha256": "school_calendar",
    "operation_source_sha256": "operation_hours",
    "class_source_sha256": "class_hours",
    "clock_source_sha256": "civil_date_time",
    "beacon_designation_source_sha256": "beacon_designation",
    "beacon_configuration_source_sha256": "beacon_lamp_configuration",
    "beacon_history_source_sha256": "beacon_lamp_history",
    "sign_source_sha256": "sign_active_period",
}


def instant(value, name):
    if not isinstance(value, str):
        raise ValueError("source-bound timestamp missing: " + name)
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("valid source-bound timestamp required: " + name) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("offset-aware source-bound timestamp required: " + name)
    return result


def derive(packet, records):
    if not isinstance(packet, dict) or packet.get("source_kind") != "original_school_clock_and_device":
        raise ValueError("original independent school clock/device packet required")
    for field, name in HASH_FIELDS.items():
        if packet.get(field) != records[name]["sha256"]:
            raise ValueError("independent source hash mismatch: " + name)
    now = instant(packet.get("local_datetime"), "local clock")
    end = instant(packet.get("operation_end_local"), "operation end")
    next_start = instant(packet.get("next_operation_start_local"), "next start")
    class_start = instant(packet.get("class_start_local"), "class start")
    class_end = instant(packet.get("class_end_local"), "class end")
    if not end < next_start or not class_start < class_end:
        raise ValueError("original school schedule ordering invalid")
    for name in ("school_in_session_today", "operational_beacon_designation",
                 "sign_limit_active", "beacon_alternating_capable"):
        if type(packet.get(name)) is not bool:
            raise ValueError("original independent school/device fact missing: " + name)
    count = packet.get("beacon_yellow_lamp_count")
    if type(count) is not int or count < 0:
        raise ValueError("original beacon lamp count required")
    history = packet.get("beacon_lamp_history")
    if not isinstance(history, list) or len(history) < 4 or any(
            not isinstance(row, list) or len(row) != count or any(type(v) is not bool for v in row)
            for row in history):
        raise ValueError("original per-lamp history required")
    alternating_observed = count >= 2 and all(sum(row) == 1 for row in history) and all(
        history[i] != history[i - 1] for i in range(1, len(history)))
    outside_operation = end + timedelta(minutes=30) <= now <= next_start - timedelta(minutes=30)
    return {
        "school_in_session_today": packet["school_in_session_today"],
        "after_operation_half_hour": end + timedelta(minutes=30) <= now < next_start,
        "before_next_start_half_hour": end < now <= next_start - timedelta(minutes=30),
        "near_after_operation_boundary": end + timedelta(minutes=30) <= now < end + timedelta(minutes=60),
        "near_before_next_start_boundary": next_start - timedelta(minutes=60) < now <= next_start - timedelta(minutes=30),
        "outside_operation_half_hour": outside_operation,
        "during_class": class_start <= now <= class_end,
        "operational_beacon_designation": packet["operational_beacon_designation"],
        "beacon_definition_supported": count >= 2 and packet["beacon_alternating_capable"],
        "alternating_flash_observed": alternating_observed,
        "sign_limit_active": packet["sign_limit_active"],
        "source_limit": "Derived source facts do not alone resolve statutory applicability or physical validity",
    }
