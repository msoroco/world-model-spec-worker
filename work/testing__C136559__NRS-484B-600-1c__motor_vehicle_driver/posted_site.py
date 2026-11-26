"""Fail-closed review of a proposed posted-speed Native site packet.

This validates source provenance and engineering consistency before a capture.
It never decides legal applicability or asserts that a sign is physically seen.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


CASES = (
    "below", "above", "equal", "outside_zone", "opposite_direction",
    "non_authority_sign", "metric_equivalent", "sign_not_in_view",
)
SOURCE_FIELDS = (
    "highway_dedication_source", "public_access_source",
    "narrow_road_geometry_source", "vehicle_clearance_source",
    "governed_segment_source", "governed_direction_source",
    "sign_position_source", "posting_authority_source",
)


def load(path: Path, expected_sha256: str, case_id: str) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed posted-speed site hash mismatch")
    packet = json.loads(raw)
    if packet.get("case_id") != case_id or packet.get("source_kind") != "reviewed_original_site":
        raise ValueError("reviewed original site identity missing")
    if not all(isinstance(packet.get(key), str) and packet[key] for key in SOURCE_FIELDS):
        raise ValueError("posted-speed site provenance incomplete")
    for key in ("governed_road_id", "governed_segment_id", "governed_direction",
                "vehicle_id", "sign_id", "sign_jurisdiction", "sign_installation_record"):
        if not isinstance(packet.get(key), str) or not packet[key]:
            raise ValueError("posted-speed site identity incomplete: " + key)
    if packet.get("unit") not in ("mph", "km/h", "m/s") or type(packet.get("rate")) not in (int, float) or packet["rate"] <= 0:
        raise ValueError("posted-speed rate or unit invalid")
    if type(packet.get("public_authority_posted")) is not bool:
        raise ValueError("public-authority status missing")
    if type(packet.get("sign_in_camera_view")) is not bool:
        raise ValueError("sign visibility remains unreviewed")
    if not packet["sign_in_camera_view"] and not packet.get("off_camera_reading_assumption_source"):
        raise ValueError("off-camera governing limit remains unknown without reading assumption")
    lanes = packet.get("travel_lanes")
    if not isinstance(lanes, dict) or not all(isinstance(lanes.get(direction), str) and lanes[direction] for direction in ("forward", "opposite")):
        raise ValueError("both actual travel directions need reviewed lane identities")
    if lanes["forward"] == lanes["opposite"]:
        raise ValueError("opposite travel requires a distinct reviewed lane")
    return packet
