"""Require an original reviewed highway packet before live construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


REQUIRED = (
    "map_name", "map_sha256", "public_highway_source", "public_access_source",
    "highway_boundaries_source", "sidewalk_inventory_source",
    "subsection_6_review_source", "walking_segment", "reviewer",
    "opendrive_source", "routes", "cameras", "centerline_xy_m",
)


def load_reviewed_site(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("missing reviewed original highway source packet")
    packet = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if not packet.get(key)]
    if missing:
        raise ValueError("incomplete reviewed original highway source packet: " + ", ".join(missing))
    for key in ("public_highway_source", "public_access_source", "highway_boundaries_source", "sidewalk_inventory_source", "subsection_6_review_source", "opendrive_source"):
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
    if hashlib.sha256((path.parent / packet["opendrive_source"]["path"]).read_bytes()).hexdigest() != packet["map_sha256"]:
        raise ValueError("reviewed OpenDRIVE map hash differs")
    centerline = packet["centerline_xy_m"]
    if not isinstance(centerline, list) or len(centerline) != 2 or any(not isinstance(point, list) or len(point) != 2 for point in centerline):
        raise ValueError("reviewed highway centerline missing")
    return packet
