"""Bind a saved right-pass route request to the map loaded in one CARLA attempt.

The caller supplies an already acquired world. This module does not import or
start CARLA, spawn actors, or treat the loaded map as proof of highway status.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pass_right_route import build_case, load_map_packet


def bind_live_route(world: object, packet_path: Path, packet_sha256: str,
                    variant: str) -> dict:
    """Return an exact route only when saved and loaded map identities agree."""
    packet = load_map_packet(packet_path, packet_sha256)
    expected_name = packet.get('map_name')
    expected_opendrive = packet.get('source_opendrive_sha256')
    if not isinstance(expected_name, str) or not expected_name:
        raise ValueError('source map name required')
    if not isinstance(expected_opendrive, str) or len(expected_opendrive) != 64:
        raise ValueError('source OpenDRIVE sha256 required')
    loaded = world.get_map()
    if loaded.name != expected_name:
        raise ValueError('loaded map identity differs from source packet')
    opendrive = loaded.to_opendrive()
    if not isinstance(opendrive, str) or not opendrive:
        raise ValueError('loaded OpenDRIVE source missing')
    actual_opendrive = hashlib.sha256(opendrive.encode('utf-8')).hexdigest()
    if actual_opendrive != expected_opendrive:
        raise ValueError('loaded OpenDRIVE sha256 differs from source packet')
    request = build_case(packet, variant)
    return {
        'case_variant': variant,
        'map_name': expected_name,
        'map_packet_sha256': packet_sha256,
        'loaded_opendrive_sha256': actual_opendrive,
        'route_request': request,
        'requires_live_actor_and_camera_checks': True,
        'physical_acceptance_claimed': False,
    }
