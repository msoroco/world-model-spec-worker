"""Require retained highway and official overhead-device sources before Native use."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(packet_path, *, source_root):
    packet_path, root = Path(packet_path), Path(source_root)
    root_resolved = root.resolve()
    if (packet_path.is_symlink() or not packet_path.is_file() or
            not packet_path.resolve().is_relative_to(root_resolved)):
        raise ValueError("reviewed packet escapes retained source root")
    packet = json.loads(packet_path.read_text())
    if packet.get("review_status") != "reviewed":
        raise ValueError("highway and official-device review not completed")
    for key in ("highway", "official_device"):
        item = packet.get(key)
        if not isinstance(item, dict):
            raise ValueError(key + " source descriptor missing")
        rel = item.get("source_path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(key + " source path is not retained locally")
        source = root / rel
        if source.is_symlink() or not source.resolve().is_relative_to(root_resolved):
            raise ValueError(key + " original source escapes retained root")
        if not source.is_file() or _sha(source) != item.get("source_sha256"):
            raise ValueError(key + " original source missing or changed")
        if not item.get("reviewer") or not item.get("source_citation"):
            raise ValueError(key + " review provenance missing")
    if packet["highway"].get("status") != "public_highway_reviewed":
        raise ValueError("public highway status unreviewed")
    device = packet["official_device"]
    if (device.get("device_kind") != "official_overhead_lane_signal" or
            device.get("symbol") != "red_x" or device.get("faces_bus") is not True or
            device.get("governed_lane_id") != "red_lane" or
            not isinstance(device.get("native_asset_blueprint_id"), str) or
            not device["native_asset_blueprint_id"]):
        raise ValueError("red-X device, facing or lane association unreviewed")
    state = device.get("native_display_state")
    if (not isinstance(state, dict) or not isinstance(state.get("attribute"), str) or
            not state["attribute"] or not isinstance(state.get("red_x_value"), str) or
            not state["red_x_value"] or not state.get("source_citation")):
        raise ValueError("reviewed Native red-X display attribute and value required")
    return {"reviewed_packet_sha256": _sha(packet_path),
            "highway_source_sha256": packet["highway"]["source_sha256"],
            "official_device_source_sha256": device["source_sha256"],
            "native_asset_blueprint_id": device["native_asset_blueprint_id"],
            "native_display_state": state,
            "governed_lane_id": device["governed_lane_id"],
            "legal_judgment": "unresolved"}
