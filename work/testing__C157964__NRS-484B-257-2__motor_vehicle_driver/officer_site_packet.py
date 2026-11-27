"""Admit only a reviewed original map and officer-control source packet.

Packet fields are plans for Native acquisition, not proof of officer activity.
The saved measurement still requires original video and independent review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from officer_scene import validate_site


REQUIRED = ("map_opendrive", "jurisdiction", "intersection_geometry",
            "entrance_controls", "officer_location",
            "officer_directive_visibility", "other_obligation",
            "ego_route", "other_route", "camera_sightlines")


def validate_packet(path: Path, expected_case: str) -> dict:
    path = Path(path)
    packet = json.loads(path.read_text())
    if packet.get("format") != "c157964-reviewed-officer-site-v1":
        raise ValueError("wrong officer site packet format")
    if packet.get("case_id") != expected_case or \
            packet.get("law_id") != "NRS-484B-257-2":
        raise ValueError("wrong exact officer case or law")
    sources = packet.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed source inventory missing")
    for name in REQUIRED:
        entry = sources.get(name)
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("original source missing: " + name)
        rel = Path(entry["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("original source outside reviewed packet: " + name)
        raw = (path.parent / rel).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry.get("sha256"):
            raise ValueError("reviewed source changed: " + name)
        if name != "map_opendrive" and packet.get(name + "_source_sha256") != digest:
            raise ValueError("reviewed scene/source join differs: " + name)
    validate_site(packet)
    if packet.get("non_through_highway") is not True or \
            packet.get("officer_visible_from_ego_approach") is not True:
        raise ValueError("non-through classification or officer sightline unreviewed")
    entrances = packet.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2 or \
            any(not isinstance(row, dict) or not row.get("id") or
                row.get("control") not in ("stop", "yield", "none") or
                not row.get("reviewed_source") for row in entrances):
        raise ValueError("all entrance controls must be reviewed")
    return packet
