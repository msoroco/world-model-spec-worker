"""Source-shaped passenger-zone measurement for NRS 484B.503.

This reports observed timelines. It never decides whether a transfer was
"expeditious" or whether a marked zone was legally established.
"""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo

FRAME_RATE = 20
FRAME_COUNT = 600


def _minutes(clock: str) -> int:
    try:
        hour, minute = map(int, clock.split(":"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid sign hours") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("invalid sign hours")
    return hour * 60 + minute


def sign_effective(civil_timestamp: str, zone: dict) -> bool:
    """Interpret an explicit sourced sign schedule using its civil time zone."""
    if not zone.get("sign_source") or not zone.get("time_zone"):
        raise ValueError("sign and time-zone provenance required")
    try:
        instant = datetime.fromisoformat(civil_timestamp)
        if instant.tzinfo is None:
            raise ValueError("civil timestamp must include offset")
        local = instant.astimezone(ZoneInfo(zone["time_zone"]))
    except (TypeError, KeyError) as exc:
        raise ValueError("invalid civil timestamp or time zone") from exc
    start, end = _minutes(zone.get("hours_start")), _minutes(zone.get("hours_end"))
    if start == end:
        raise ValueError("ambiguous equal sign hours")
    now = local.hour * 60 + local.minute
    return start <= now < end if start < end else now >= start or now < end


def measure_loading(rows: list[dict], zone: dict) -> dict:
    """Join pose, door and passenger observations over a 30-second episode."""
    if len(rows) != FRAME_COUNT:
        raise ValueError("loading trace must contain 600 frames")
    if zone.get("kind") != "passenger_curb_loading" or not zone.get("curb_source"):
        raise ValueError("passenger curb zone provenance required")
    halted = []
    in_zone = []
    door = []
    transfer = []
    active = []
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("frame identity or 20 Hz join failed")
        speed = row.get("vehicle_speed_mps")
        if not isinstance(speed, (int, float)) or not isfinite(speed) or speed < 0:
            raise ValueError("raw vehicle speed required")
        for key in ("vehicle_in_marked_zone", "door_open", "passenger_crossed_doorway"):
            if type(row.get(key)) is not bool:
                raise ValueError("raw zone, door and passenger sources required")
        if not row.get("occupant_count_source") or type(row.get("occupant_count")) is not int or row["occupant_count"] < 0:
            raise ValueError("occupant count source required")
        halted.append(speed <= 0.05)  # engineering motion classification, not statutory grace
        in_zone.append(row["vehicle_in_marked_zone"])
        door.append(row["door_open"])
        transfer.append(row["passenger_crossed_doorway"])
        active.append(sign_effective(row.get("civil_timestamp"), zone))
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "halted_in_zone_frames": sum(h and z for h, z in zip(halted, in_zone)),
        "effective_hours_frames": sum(active),
        "door_open_frames": sum(door),
        "observed_doorway_transfer_frames": sum(transfer),
        "transfer_during_halt_in_zone_frames": sum(t and h and z for t, h, z in zip(transfer, halted, in_zone)),
        "legal_expeditiousness_conclusion": None,
        "zone_validity_conclusion": None,
        "source_kind": "unverified_raw_fields",
    }


def audit_selected_pair(loading_rows: list[dict], no_transfer_rows: list[dict], zone: dict) -> dict:
    """Check the selected comparison changes only passenger transfer evidence.

    This is an isolation check on supplied raw fields, not an opinion that a
    marked zone or transfer happened in CARLA.
    """
    if len(loading_rows) != FRAME_COUNT or len(no_transfer_rows) != FRAME_COUNT:
        raise ValueError("selected pair must contain 600 frames per condition")
    variable = {"passenger_crossed_doorway", "occupant_count"}
    for first, second in zip(loading_rows, no_transfer_rows):
        if set(first) != set(second):
            raise ValueError("selected pair source channels differ")
        if {key: value for key, value in first.items() if key not in variable} != {key: value for key, value in second.items() if key not in variable}:
            raise ValueError("selected pair changed fixed zone, time, vehicle or door fields")
    loading = measure_loading(loading_rows, zone)
    no_transfer = measure_loading(no_transfer_rows, zone)
    if loading["transfer_during_halt_in_zone_frames"] < 1 or no_transfer["transfer_during_halt_in_zone_frames"] != 0:
        raise ValueError("selected pair lacks isolated passenger transfer")
    if loading_rows[0]["occupant_count"] == loading_rows[-1]["occupant_count"] or no_transfer_rows[0]["occupant_count"] != no_transfer_rows[-1]["occupant_count"]:
        raise ValueError("selected pair occupant exchange differs from transfer branch")
    return {"loading": loading, "no_transfer": no_transfer,
            "comparison_variable": "actual_passenger_loading",
            "isolation_checked": True, "physical_transfer_confirmed": False}
