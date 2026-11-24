"""Bind a reviewed exact site to original Native event acquisition.

The operator owns world settings, traffic actors, sensors and restoration. This
module copies original source packets into the attempt and destroys its ego.
It does not claim that event readback supplies the four camera streams.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from original_capture import capture_original
from signal_exception import construct_native, sealed, verify_site


def capture_events(session, site_path, case_id, attempt):
    site_path = Path(site_path)
    source_root = site_path.parent
    site_bytes = site_path.read_bytes()
    site = json.loads(site_bytes)
    if site.get("diagnostic_fixture") is not False or site.get("case_id") != case_id:
        raise ValueError("Reviewed exact Native site packet required")
    verify_site(site, source_root)
    attempt = Path(attempt)
    if not attempt.is_dir():
        raise ValueError("Materialized attempt directory required")
    reserved = {"native-site.json", "original-events.json", "event-receipt.json"}
    source_paths = {}
    for key, ref in site["original_sources"].items():
        relative = Path(ref["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Original source path escapes site")
        if str(relative) in source_paths or str(relative) in reserved:
            raise ValueError("Duplicate or reserved original source path")
        source_paths[str(relative)] = sealed(ref, source_root)
    if any((attempt / name).exists() for name in reserved | set(source_paths)):
        raise ValueError("Original attempt source already exists")
    native = None
    try:
        native = construct_native(site, source_root, session.world, session.carla,
                                  session.blueprint_library)
        (attempt / "native-site.json").write_bytes(site_bytes)
        for relative, source in source_paths.items():
            target = attempt / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        receipt = capture_original(site, attempt, session.event_adapter,
                                   attempt / "original-events.json")
        receipt.update({"case_id": case_id,
                        "site_packet_sha256": hashlib.sha256(site_bytes).hexdigest(),
                        "original_source_sha256": {key: ref["sha256"] for key, ref in site["original_sources"].items()},
                        "camera_media_status": "not_acquired_by_event_session"})
        (attempt / "event-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        return receipt
    finally:
        if native is not None:
            native["ego"].destroy()
