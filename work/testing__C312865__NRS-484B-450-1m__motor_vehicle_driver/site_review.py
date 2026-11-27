"""Reject unsourced tunnel, highway, route and exception packets before Native capture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tunnel import CASES, validate_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path: Path, case_id: str):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("reviewed original tunnel packet missing")
    path = path.resolve()
    packet = json.loads(path.read_text(encoding="utf-8"))
    case = next((item for item in CASES if case_id.endswith("__" + item.case_id)), None)
    if case is None or packet.get("case_id") != case_id:
        raise ValueError("reviewed tunnel packet exact case mismatch")
    if (packet.get("review_status") != "reviewed_original_source" or
            packet.get("diagnostic_fixture") is not False or
            not packet.get("reviewer") or not packet.get("review_method")):
        raise ValueError("reviewed original tunnel provenance missing")
    sources = packet.get("sources")
    required = {"map", "highway", "tunnel", "portal", "route",
                "ego_blueprint", "other_blueprint", "authority"}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError("reviewed tunnel source inventory incomplete")
    for name, source in sources.items():
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise ValueError("reviewed source identity missing: " + name)
        raw_target = path.parent / source["path"]
        target = raw_target.resolve()
        if (not target.is_relative_to(path.parent) or not target.is_file() or
                raw_target.is_symlink() or sha(target) != source["sha256"]):
            raise ValueError("reviewed tunnel source changed: " + name)
    map_record = json.loads((path.parent / sources["map"]["path"]).read_text())
    if (packet.get("map_id") != map_record.get("map_id") or
            len(map_record.get("opendrive_sha256", "")) != 64):
        raise ValueError("reviewed tunnel map identity missing")
    site = packet.get("site")
    if not isinstance(site, dict):
        raise ValueError("reviewed tunnel site absent")
    validate_site(site)
    for field, name in (
        ("map_source_sha256", "map"), ("highway_source_sha256", "highway"),
        ("tunnel_source_sha256", "tunnel"), ("portal_source_sha256", "portal"),
        ("route_source_sha256", "route"),
        ("ego_blueprint_source_sha256", "ego_blueprint"),
        ("other_blueprint_source_sha256", "other_blueprint"),
    ):
        if site[field] != sources[name]["sha256"]:
            raise ValueError("reviewed tunnel site does not bind source bytes: " + field)
    for name in ("ego_blueprint_id", "other_blueprint_id"):
        if not packet.get(name, "").startswith("vehicle."):
            raise ValueError("motor vehicle blueprint missing: " + name)
    if case.exception_probe and not packet.get("authority_record_id"):
        raise ValueError("original exception authority record missing")
    return packet, case
