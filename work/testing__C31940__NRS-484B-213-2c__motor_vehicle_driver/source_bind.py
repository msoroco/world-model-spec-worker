"""Bind a reviewed bridge packet to original source bytes before live construction."""
from __future__ import annotations

import hashlib
from pathlib import Path

REQUIRED = {"map", "highway", "centerline", "lane_forward", "ego_vehicle",
            "bridge", "bridge_entrance", "view_geometry", "camera_plan"}


def bind(packet, root):
    root = Path(root).resolve()
    entries = packet.get("sources")
    if not isinstance(entries, list):
        raise ValueError("reviewed original source inventory missing")
    roles = [item.get("role") for item in entries if isinstance(item, dict)]
    if len(roles) != len(set(roles)) or not REQUIRED <= set(roles):
        raise ValueError("reviewed bridge source roles missing or duplicated")
    if not packet["road"]["one_way_highway"] and "lane_reverse" not in roles:
        raise ValueError("opposite-direction lane source missing")
    if packet.get("opaque_blocker") and "opaque_blocker" not in roles:
        raise ValueError("opaque blocker source missing")
    bound = {}
    for item in entries:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("unversioned reviewed source entry")
        path = root / item["path"]
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("reviewed original source path missing or escapes root")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError("reviewed original source bytes changed")
        bound[item["role"]] = {"path": str(path), "sha256": actual}
    if bound["map"]["sha256"] != packet.get("map_opendrive_sha256"):
        raise ValueError("reviewed map differs from Native setup")
    road = packet["road"]
    for role, key in (("centerline", "centerline_source_sha256"),
                      ("bridge", "bridge_source_sha256")):
        if bound[role]["sha256"] != road.get(key):
            raise ValueError("reviewed " + role + " differs from Native setup")
    return bound
