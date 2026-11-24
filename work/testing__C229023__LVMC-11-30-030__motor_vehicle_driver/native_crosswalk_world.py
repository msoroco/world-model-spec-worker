"""Bind a reviewed crosswalk source map to a synchronous Native world session."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID


def _map_hash(world):
    description = world.get_map().to_opendrive()
    if not isinstance(description, str) or not description:
        raise ValueError("Native world lacks original OpenDRIVE readback")
    return hashlib.sha256(description.encode("utf-8")).hexdigest()


def run_sourced_world(*, world, proposal: dict, capture):
    """Run caller-owned actor/camera capture only on a matching 20 Hz map.

    The callable owns spawning, controller, original pixel encoding and cleanup.
    This wrapper checks site bytes and Native map/settings before any capture.
    """
    if not isinstance(proposal, dict) or proposal.get("assignment_id") != ASSIGNMENT_ID:
        raise ValueError("source-bound exact assignment proposal required")
    source = proposal.get("source")
    inventory = proposal.get("source_inventory")
    if not isinstance(source, dict) or not isinstance(inventory, dict) or "map" not in inventory:
        raise ValueError("site and map source inventory required")
    site_path = Path(source.get("path", ""))
    if site_path.is_symlink() or not site_path.is_file() or hashlib.sha256(site_path.read_bytes()).hexdigest() != source.get("sha256"):
        raise ValueError("original site packet changed")
    entry = inventory["map"]
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or len(Path(entry["path"]).parts) != 1:
        raise ValueError("portable original map source required")
    map_path = site_path.parent / entry["path"]
    if map_path.is_symlink() or not map_path.is_file() or hashlib.sha256(map_path.read_bytes()).hexdigest() != entry.get("sha256"):
        raise ValueError("original map source changed")
    if _map_hash(world) != entry["sha256"]:
        raise ValueError("loaded Native map differs from reviewed source map")
    if world.get_map().name != proposal.get("map_id"):
        raise ValueError("loaded Native map identity differs")
    if not callable(capture):
        raise ValueError("Native capture callable required")
    original = world.get_settings()
    desired = copy.copy(original)
    desired.synchronous_mode = True
    desired.fixed_delta_seconds = .05
    try:
        world.apply_settings(desired)
        active = world.get_settings()
        if active.synchronous_mode is not True or active.fixed_delta_seconds != .05:
            raise ValueError("Native world did not read back synchronous 20 Hz settings")
        result = capture(world)
        if _map_hash(world) != entry["sha256"]:
            raise ValueError("Native map changed during crosswalk capture")
        return {"case_id": proposal["case_id"], "map_sha256": entry["sha256"],
                "capture_result": result, "physical_acceptance_claimed": False}
    finally:
        world.apply_settings(original)
