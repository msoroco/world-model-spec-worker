"""Validate reviewed original site sources before Native rider construction.

The worker does not supply a municipal site or decide whether its path is
legally usable. A local reviewer must provide the source-hashed packet.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from path_observation import ASSIGNMENT, DEVICES
from path_route import select_route


REQUIRED = ("municipal_jurisdiction", "map_geometry", "path_designation",
            "path_adjacency", "sidewalk_absence", "path_condition",
            "path_access", "device_classification")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reviewed_site(manifest_path: str | Path, site_path: str | Path,
                       case_id: str, device: str, target: str,
                       condition: str) -> dict:
    """Return a route only after every original source and case join passes."""
    manifest_path = Path(manifest_path)
    site_path = Path(site_path)
    manifest = json.loads(manifest_path.read_text())
    site = json.loads(site_path.read_text())
    if (not case_id.startswith(ASSIGNMENT + "__") or
            manifest.get("assignment_id") != ASSIGNMENT or
            manifest.get("case_id") != case_id or
            site.get("assignment_id") != ASSIGNMENT or
            site.get("case_id") != case_id):
        raise ValueError("reviewed original case identity required")
    if manifest.get("source_kind") != "reviewed_original" or manifest.get("synthetic") is not False:
        raise ValueError("reviewed original source provenance required")
    if manifest.get("site_sha256") != sha(site_path):
        raise ValueError("reviewed site source hash mismatch")
    if site.get("ego_device_type") != device or device not in DEVICES:
        raise ValueError("reviewed covered device classification required")
    if site.get("path_usability_status") != condition or condition not in ("usable", "unusable"):
        raise ValueError("reviewed path condition case mismatch")
    if site.get("municipal_jurisdiction_reviewed") is not True:
        raise ValueError("reviewed municipal jurisdiction required")
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(REQUIRED):
        raise ValueError("complete original site source inventory required")
    for name in REQUIRED:
        item = sources[name]
        relative = Path(item.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("unsafe original source path: " + name)
        source = manifest_path.parent / relative
        if not source.is_file() or source.is_symlink() or sha(source) != item.get("sha256"):
            raise ValueError("missing or changed original source: " + name)
    route = select_route(site_path, target, target)
    if route["path_usability_status"] != condition:
        raise ValueError("route path condition mismatch")
    return {"site": site, "route": route, "manifest_sha256": sha(manifest_path),
            "site_sha256": sha(site_path), "source_sha256":
            {name: sources[name]["sha256"] for name in REQUIRED},
            "physical_path_usability_verified": False,
            "legal_judgment": None}
