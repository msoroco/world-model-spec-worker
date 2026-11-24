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


def verify_live_map(world, packet_path: Path, case_id: str) -> dict:
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text())
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
    return {"format": "worker-400-2a-live-map-binding-v1",
            "case_id": case_id, "map_name": map_object.name,
            "opendrive_sha256": digest,
            "survey_packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "planned_construction": planned,
            "public_highway_reviewed": False,
            "physical_completion": False}
