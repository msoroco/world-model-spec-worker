"""Bind a reviewed Native packet to original source bytes before live construction."""
from __future__ import annotations

import hashlib
from pathlib import Path

REQUIRED = {"map", "highway", "centerline", "lane_forward", "lane_reverse",
            "ego_vehicle", "overtaken_vehicle", "camera_plan"}


def bind(packet, root):
    root = Path(root).resolve()
    entries = packet.get("sources")
    if not isinstance(entries, list):
        raise ValueError("reviewed original source inventory missing")
    roles = [entry.get("role") for entry in entries if isinstance(entry, dict)]
    if len(roles) != len(set(roles)) or not REQUIRED <= set(roles):
        raise ValueError("reviewed source roles missing or duplicated")
    if "oncoming" in packet.get("actors", {}) and "oncoming_vehicle" not in roles:
        raise ValueError("oncoming original source missing")
    if packet.get("case_id", "").endswith("occluded_left") and "opaque_blocker" not in roles:
        raise ValueError("opaque blocker original source missing")
    bound = {}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
            raise ValueError("unversioned reviewed source entry")
        candidate = root / entry["path"]
        if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            raise ValueError("reviewed original source path missing or escapes root")
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError("reviewed original source bytes changed")
        bound[entry["role"]] = {"path": str(candidate), "sha256": actual}
    if bound["map"]["sha256"] != packet.get("map_opendrive_sha256"):
        raise ValueError("reviewed map source hash differs from Native setup")
    if bound["centerline"]["sha256"] != packet.get("road", {}).get("centerline_source_sha256"):
        raise ValueError("reviewed centerline source hash differs from Native setup")
    return bound
