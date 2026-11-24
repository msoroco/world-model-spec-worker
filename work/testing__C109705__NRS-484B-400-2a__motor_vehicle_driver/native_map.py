"""Bind a reviewed exact intersection packet to the loaded Native OpenDRIVE.

The packet's public-highway assertion still requires an external source review;
this only verifies that the Native map bytes and planned geometry are the same.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from approach import validate_context
from construction import build


def _reviewed_highways(packet: dict, packet_path: Path, map_digest: str,
                       context: dict) -> bool:
    review = packet.get("public_highway_review")
    if review is None:
        return False
    if not isinstance(review, dict) or review.get("status") != "reviewed":
        raise ValueError("public-highway review is not source attested")
    if (review.get("opendrive_sha256") != map_digest or
            review.get("approach_road_id") != context["approach_road_id"] or
            review.get("departure_road_id") != context["departure_road_id"]):
        raise ValueError("public-highway review map or road binding differs")
    source = review.get("source")
    if not isinstance(source, dict):
        raise ValueError("public-highway review source missing")
    relative = source.get("path")
    expected = source.get("sha256")
    if not isinstance(relative, str) or not relative or not isinstance(expected, str):
        raise ValueError("public-highway review source reference missing")
    base = packet_path.parent.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("public-highway review source missing or outside packet")
    raw = path.read_bytes()
    if not raw or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("public-highway review source hash differs")
    if context.get("public_highway_source") != relative:
        raise ValueError("public-highway context source differs from review")
    return True


def verify_live_map(world, packet_path: Path, case_id: str) -> dict:
    packet_path = Path(packet_path)
    packet_bytes = packet_path.read_bytes()
    packet = json.loads(packet_bytes)
    map_object = world.get_map()
    opendrive = map_object.to_opendrive()
    if not isinstance(opendrive, str) or not opendrive.strip():
        raise ValueError("Native OpenDRIVE source missing")
    digest = hashlib.sha256(opendrive.encode()).hexdigest()
    if digest != packet.get("source_sha256"):
        raise ValueError("loaded Native OpenDRIVE hash differs from survey")
    if map_object.name != packet.get("map_name"):
        raise ValueError("loaded Native map identity differs from survey")
    context = packet.get("context")
    if not isinstance(context, dict):
        raise ValueError("original intersection context missing")
    validate_context(context)
    planned = build(case_id, packet)
    reviewed = _reviewed_highways(packet, packet_path, digest, context)
    return {"format": "worker-400-2a-live-map-binding-v1",
            "case_id": case_id, "map_name": map_object.name,
            "opendrive_sha256": digest,
            "survey_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            "intersection_context": context,
            "planned_construction": planned,
            "public_highway_reviewed": reviewed,
            "physical_completion": False}
