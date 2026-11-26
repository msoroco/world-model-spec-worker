"""Validate an independent restricted-zone survey before Native construction.

The packet is an input to local capture, never a worker assertion that a zone is
legally effective. Every asserted source is copied and hash checked at capture.
"""

import hashlib
import json
from pathlib import Path


ROLES = ("zone_sign", "zone_authority", "zone_boundaries", "effective_conditions",
         "stopping_exclusions", "subject_vehicle_class", "driver_identity",
         "entrant_vehicle_class", "entrant_parking_task", "passenger_exchange_method")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(path, case_id, plan):
    path = Path(path).resolve()
    packet = json.loads(path.read_text())
    if packet.get("case_id") != case_id or packet.get("cell_id") != "C135087":
        raise ValueError("reviewed site case/cell mismatch")
    if packet.get("map_id") != plan.map_id:
        raise ValueError("reviewed site map mismatch")
    if packet.get("restricted_purpose") != plan.restricted_purpose:
        raise ValueError("reviewed restricted purpose mismatch")
    for key in ("zone_start_m", "zone_end_m"):
        if packet.get(key) != getattr(plan, key):
            raise ValueError("reviewed zone boundary mismatch")
    sources = packet.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(ROLES):
        raise ValueError("reviewed site source roles incomplete")
    for role, item in sources.items():
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("reviewed site source reference incomplete: " + role)
        source = Path(item["path"])
        if not source.is_absolute():
            source = path.parent / source
        source = source.resolve()
        if not source.is_file() or sha(source) != item["sha256"]:
            raise ValueError("reviewed site source missing or stale: " + role)
    if not packet.get("reviewer") or not packet.get("reviewed_at"):
        raise ValueError("independent site review identity missing")
    return packet
