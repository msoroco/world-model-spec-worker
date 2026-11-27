"""Require an original reviewed highway packet before live construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


REQUIRED = (
    "map_name", "map_sha256", "public_highway_source", "public_access_source",
    "highway_boundaries_source", "sidewalk_inventory_source",
    "subsection_6_review_source", "walking_segment", "reviewer",
)


def load_reviewed_site(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("missing reviewed original highway source packet")
    packet = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if not packet.get(key)]
    if missing:
        raise ValueError("incomplete reviewed original highway source packet: " + ", ".join(missing))
    for key in ("public_highway_source", "public_access_source", "highway_boundaries_source", "sidewalk_inventory_source", "subsection_6_review_source"):
        source = packet[key]
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise ValueError("missing original source binding: " + key)
        source_path = path.parent / source["path"]
        if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("missing or stale original source: " + key)
    if packet.get("reviewed_public_highway") is not True:
        raise ValueError("public highway status unresolved")
    if packet.get("reviewed_sidewalk_absent") is not True:
        raise ValueError("qualifying sidewalk absence unresolved")
    if packet.get("reviewed_subsection_6_inapplicable") is not True:
        raise ValueError("subsection 6 exception unresolved")
    return packet
