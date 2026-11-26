"""Check reviewed source bytes embedded in a delivery construction.

This verifies byte custody against a separate preflight receipt; it does not
judge whether a reviewer's statutory findings are correct.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath

SOURCE_KEYS = ("public_access_source", "device_inventory_source", "driver_scope_source")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def files_by_path(document: dict) -> dict[str, str]:
    result = {}
    for item in document.get("files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
            raise ValueError("invalid inline reviewed construction file")
        path = item["path"]
        if path in result:
            raise ValueError("duplicate inline reviewed construction path")
        result[path] = item["content"]
    return result


def verify(files: dict[str, str], scene: dict, preflight: dict) -> dict[str, str]:
    packet_path = scene.get("reviewed_context_source")
    if not isinstance(packet_path, str):
        raise ValueError("inline reviewed packet path missing")
    packet_rel = PurePosixPath(packet_path)
    if packet_rel.is_absolute() or ".." in packet_rel.parts or not packet_rel.parts:
        raise ValueError("inline reviewed packet path invalid")
    packet_text = files.get(packet_path)
    if not isinstance(packet_text, str):
        raise ValueError("inline reviewed packet bytes missing")
    packet = json.loads(packet_text)
    law = packet.get("law_context")
    if not isinstance(law, dict):
        raise ValueError("inline reviewed law context missing")
    retained = preflight.get("retained_source_hashes")
    if not isinstance(retained, dict) or set(retained) != set(SOURCE_KEYS):
        raise ValueError("preflight retained reviewed sources incomplete")
    result = {}
    for key in SOURCE_KEYS:
        descriptor = law.get(key)
        if not isinstance(descriptor, dict):
            raise ValueError("inline reviewed source descriptor missing: " + key)
        rel = descriptor.get("source_path")
        if not isinstance(rel, str) or not rel or not descriptor.get("reviewer") or not descriptor.get("source_citation"):
            raise ValueError("inline reviewed source provenance missing: " + key)
        source_rel = PurePosixPath(rel)
        if source_rel.is_absolute() or ".." in source_rel.parts:
            raise ValueError("inline reviewed source path invalid: " + key)
        path = (packet_rel.parent / source_rel).as_posix()
        content = files.get(path)
        if not isinstance(content, str):
            raise ValueError("inline reviewed source bytes missing: " + key)
        value = digest(content)
        if value != descriptor.get("source_sha256") or value != retained[key]:
            raise ValueError("inline reviewed source differs from preflight: " + key)
        result[key] = value
    return result
