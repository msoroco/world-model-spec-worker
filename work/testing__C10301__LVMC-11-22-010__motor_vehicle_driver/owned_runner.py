"""Bind a reviewed alley site to the two exact diagnostic Native captures.

The operator-owned session controls world settings, cameras and restoration.
This entrypoint preserves the reviewed site bytes and always destroys its ego.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_capture import capture
from native_operation import CASE_PROFILES, spawn_ego


def capture_reviewed(session, site_path, case_id, output_dir):
    if case_id not in CASE_PROFILES:
        raise ValueError("Unknown exact alley case")
    site_path = Path(site_path)
    source = site_path.read_bytes()
    site = json.loads(source)
    if site.get("diagnostic_fixture") is not False:
        raise ValueError("Reviewed original site packet required")
    output_dir = Path(output_dir)
    if output_dir.exists():
        if not output_dir.is_dir() or not (output_dir / "config.json").is_file() or not (output_dir / "runner.py").is_file():
            raise ValueError("Capture output already exists outside a materialized bundle")
        for name in ("camera-png", "ego.jsonl", "context.jsonl", "operation.jsonl",
                     "camera-frame-map.jsonl", "capture.json", "site-source.json"):
            if (output_dir / name).exists():
                raise ValueError("Capture output already contains original acquisition: " + name)
    if not getattr(session, "person_id", None):
        raise ValueError("Original operator identity required")
    output_dir.mkdir(parents=True, exist_ok=True)
    actor = None
    try:
        actor = spawn_ego(session.world, session.carla, site, case_id)
        result = capture(session.capture_adapter, actor, session.carla, site,
                         case_id, session.person_id, output_dir)
        (output_dir / "site-source.json").write_bytes(source)
        result["site_packet_sha256"] = hashlib.sha256(source).hexdigest()
        (output_dir / "capture.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        return result
    finally:
        if actor is not None:
            actor.destroy()
