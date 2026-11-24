"""Source-gated operator entry point for one LVMC 11.16.040 Native case.

The operator supplies the CARLA world, ego, original readers and camera adapter.
No CARLA dependency is imported by this module or by its CPU tests.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sight_construction import CASES, spawn_occluder, validate_site
from native_sight_capture import capture


SOURCE_FIELDS = ("jurisdiction", "road_kind", "entering_arms", "ego_road_through",
                 "traffic_controlled_intersection", "boundary")


def read_reviewed_site(packet_path: Path, *, case_key: str, world) -> dict:
    if case_key not in CASES:
        raise ValueError("Unknown exact case")
    packet_path = Path(packet_path)
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    if packet.get("case_id") != case_key or not packet.get("reviewer"):
        raise ValueError("Reviewed site identity or reviewer missing")
    if packet.get("map_hash") != hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest():
        raise ValueError("Reviewed OpenDRIVE map hash mismatch")
    refs = packet.get("source_files")
    if not isinstance(refs, dict):
        raise ValueError("Reviewed source inventory missing")
    for field in SOURCE_FIELDS:
        ref = refs.get(field)
        if not isinstance(ref, dict):
            raise ValueError("Reviewed source missing: " + field)
        name = ref.get("path")
        if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
            raise ValueError("Unsafe reviewed source path")
        source = packet_path.parent / name
        parts = [packet_path.parent.joinpath(*Path(name).parts[:i])
                 for i in range(1, len(Path(name).parts) + 1)]
        if any(part.is_symlink() for part in parts):
            raise ValueError("Symlinked reviewed source path")
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref.get("sha256") or digest != packet.get(field + "_source_sha256"):
            raise ValueError("Reviewed source hash mismatch: " + field)
        document = json.loads(data)
        if (document.get("source_kind") != field or not document.get("reviewer")
                or not document.get("source_citation")
                or (field != "boundary" and document.get("value") != packet.get(field))):
            raise ValueError("Reviewed source claim mismatch: " + field)
    validate_site(packet, CASES[case_key])
    return packet


def run_case(*, case_key: str, packet_path: Path, world, ego, route_reader,
             ray_reader, brake, camera_adapter, output: Path) -> dict:
    site = read_reviewed_site(packet_path, case_key=case_key, world=world)
    occluder = None
    started = False
    try:
        occluder = spawn_occluder(world, site, CASES[case_key])
        started = True
        camera_adapter.start()
        return capture(case_key, site, world, ego, route_reader, ray_reader,
                       brake, output, camera_reader=camera_adapter.read)
    finally:
        try:
            if started:
                camera_adapter.stop()
        finally:
            if occluder is not None:
                occluder.destroy()
