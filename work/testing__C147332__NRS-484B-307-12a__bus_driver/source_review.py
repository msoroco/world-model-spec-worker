"""Bind a retained highway and overhead green-arrow source packet.

Review provenance is checked, but the function makes no legal finding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def retained(root, item, label):
    if not isinstance(item, dict):
        raise ValueError(label + " source descriptor missing")
    rel = item.get("source_path")
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError(label + " source path must be retained locally")
    root = Path(root).resolve()
    path = root / rel
    if (path.is_symlink() or root not in path.resolve().parents or
            not path.is_file() or sha(path) != item.get("source_sha256")):
        raise ValueError(label + " original source missing or changed")
    if not item.get("reviewer") or not item.get("source_citation"):
        raise ValueError(label + " review provenance missing")
    return item["source_sha256"]


def validate(packet_path, *, source_root):
    packet_path, root = Path(packet_path), Path(source_root)
    root = root.resolve()
    if (packet_path.is_symlink() or root not in packet_path.resolve().parents or
            not packet_path.is_file()):
        raise ValueError("review packet must be retained within source root")
    packet = json.loads(packet_path.read_text())
    if packet.get("review_status") != "reviewed":
        raise ValueError("highway and official-device review not completed")
    highway = packet.get("highway")
    highway_hash = retained(root, highway, "highway")
    if highway.get("status") != "public_highway_reviewed" or not highway.get("highway_id"):
        raise ValueError("public highway identity/status unreviewed")
    device = packet.get("official_device")
    device_hash = retained(root, device, "official device")
    if (device.get("device_kind") != "official_overhead_lane_signal" or
            device.get("symbol") != "down_green_arrow" or
            device.get("faces_bus") is not True or
            device.get("placement") != "over_individual_lanes" or
            not device.get("native_asset_blueprint_id") or
            not device.get("dark_asset_blueprint_id")):
        raise ValueError("green-arrow overhead device or facing unreviewed")
    lanes = device.get("governed_lane_ids")
    if not isinstance(lanes, list) or not lanes or len(lanes) != len(set(lanes)) or any(
            not isinstance(lane, str) or not lane for lane in lanes):
        raise ValueError("official green-arrow lane association unreviewed")
    state = device.get("native_display_state")
    if (not isinstance(state, dict) or not isinstance(state.get("attribute"), str) or
            not state["attribute"] or not isinstance(state.get("green_value"), str) or
            not state["green_value"] or not isinstance(state.get("dark_value"), str) or
            not state["dark_value"] or state["green_value"] == state["dark_value"] or
            not state.get("source_citation")):
        raise ValueError("reviewed Native green/dark display attribute and values required")
    return {"reviewed_packet_sha256": sha(packet_path),
            "highway_source_sha256": highway_hash,
            "highway_id": highway["highway_id"],
            "official_device_source_sha256": device_hash,
            "governed_lane_ids": lanes,
            "native_asset_blueprint_id": device["native_asset_blueprint_id"],
            "dark_asset_blueprint_id": device["dark_asset_blueprint_id"],
            "native_display_state": state,
            "legal_judgment": "unresolved"}
