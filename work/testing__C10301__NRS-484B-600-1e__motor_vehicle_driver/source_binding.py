"""Verify byte bindings for a supplied C10301 site packet.

This verifies provenance only. It does not decide whether an alley is a public
way, whether an access aisle exists, or whether the route is safe at speed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def verify_site_sources(packet: dict, packet_path: Path) -> dict[str, str]:
    """Require readable route and aisle sources with exact SHA-256 bindings."""
    result = {}
    for key in ("route_source_ref", "access_aisle_source_ref"):
        ref = packet.get(key)
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ValueError(f"{key} requires a path and SHA-256")
        path_text, expected = ref["path"], ref["sha256"]
        if not isinstance(path_text, str) or not path_text or not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"{key} has invalid source identity")
        try:
            int(expected, 16)
        except ValueError as exc:
            raise ValueError(f"{key} has invalid SHA-256") from exc
        path = Path(path_text)
        if not path.is_absolute():
            path = packet_path.resolve().parent / path
        if not path.is_file():
            raise ValueError(f"{key} source file missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"{key} source SHA-256 differs")
        result[key] = actual
    if result["route_source_ref"] == result["access_aisle_source_ref"]:
        raise ValueError("route and access-aisle sources must be distinct")
    return result
