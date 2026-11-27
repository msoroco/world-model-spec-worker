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
from attention_sweep_capture import AttentionSweepCapture
from reviewed_attention_intake import REQUIRED_SOURCES, validate as validate_attention


def _stage_attention_packet(packet_path: Path, output_dir: Path) -> Path:
    """Preserve the reviewed packet and its exact source bytes with the attempt."""
    packet_path = Path(packet_path)
    validate_attention(packet_path)
    packet = json.loads(packet_path.read_bytes())
    stage = output_dir / "interior-sources"
    if stage.exists():
        raise ValueError("interior source stage already exists")
    stage.mkdir()
    for key in REQUIRED_SOURCES:
        entry = packet["sources"][key]
        original = Path(entry["path"])
        if not original.is_absolute():
            original = packet_path.parent / original
        if not original.is_file() or original.is_symlink():
            raise ValueError("reviewed interior source missing or symlinked: " + key)
        raw = original.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("reviewed interior source changed: " + key)
        name = key + original.suffix
        (stage / name).write_bytes(raw)
        entry["path"] = name
    staged = stage / "packet.json"
    staged.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    validate_attention(staged)
    return staged


def capture_reviewed(session, site_path, case_id, output_dir, *, pipeline_factory=None,
                     publisher=None, attention_packet_path=None):
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
    if not getattr(session, "client", None):
        raise ValueError("Original CARLA client required for PipelineCapture")
    if attention_packet_path is None:
        raise ValueError("Reviewed original interior attention packet required")
    if pipeline_factory is None:
        from pipeline_capture import PipelineCapture
        pipeline_factory = PipelineCapture
    if publisher is None:
        from runtime_publication import publish_original
        publisher = publish_original
    output_dir.mkdir(parents=True, exist_ok=True)
    staged_attention = _stage_attention_packet(Path(attention_packet_path), output_dir)
    attention_intake = validate_attention(staged_attention)
    attention_capture = AttentionSweepCapture(
        staged_attention, case_id, attention_intake["axis"]["min"])
    actor = None
    try:
        actor = spawn_ego(session.world, session.carla, site, case_id)
        with pipeline_factory(session.client, actor, output_dir, case_id,
                              required_observations=()) as original:
            result = capture(session.capture_adapter, actor, session.carla, site,
                             case_id, session.person_id, output_dir,
                             pipeline_capture=original,
                             attention_capture=attention_capture)
        (output_dir / "site-source.json").write_bytes(source)
        result["site_packet_sha256"] = hashlib.sha256(source).hexdigest()
        (output_dir / "capture.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        result["runtime_publication"] = publisher(output_dir, case_id)
        return result
    finally:
        if actor is not None:
            actor.destroy()
