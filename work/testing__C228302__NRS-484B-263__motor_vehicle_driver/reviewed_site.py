"""Verify retained original road authority and exit geometry before CARLA use."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from controlled_access_exit import validate_site


FIELDS = {
    'map': ('road', 'map_sha256'),
    'public_dedication': ('road', 'public_dedication_source_sha256'),
    'public_access': ('road', 'public_access_source_sha256'),
    'restricted_access_authority': ('road', 'restricted_access_authority_source_sha256'),
    'restricted_access_determination': ('road', 'restricted_access_determination_source_sha256'),
    'highway_boundary': ('road', 'highway_boundary_source_sha256'),
    'exit_connection': ('road', 'exit_connection_source_sha256'),
    'route': ('road', 'route_source_sha256'),
    'ego_blueprint': (None, 'ego_blueprint_source_sha256'),
    'approach_blueprint': (None, 'approach_blueprint_source_sha256'),
    'driver_control': (None, 'driver_control_source_sha256'),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(packet_path: Path, case) -> dict:
    packet_path = Path(packet_path).resolve(strict=True)
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if (packet.get('format') != 'c228302-reviewed-exit-site-v1' or
            packet.get('source_kind') != 'original_native_capture' or
            packet.get('diagnostic_fixture') is not False or
            not packet.get('reviewer')):
        raise ValueError('reviewed original exit site packet required')
    site = packet.get('site')
    if not isinstance(site, dict):
        raise ValueError('reviewed original site context missing')
    validate_site(site, case)
    if site.get('source_kind') != 'original_native_capture' or not site.get('reviewer'):
        raise ValueError('reviewed original site context required')
    road_ids = site['road'].get('highway_road_ids')
    if not isinstance(road_ids, list) or not road_ids or any(type(value) is not int for value in road_ids):
        raise ValueError('reviewed approaching highway road IDs required')
    bindings = packet.get('source_bindings')
    if not isinstance(bindings, dict) or set(bindings) != set(FIELDS):
        raise ValueError('complete original source bindings required')
    paths = {}
    for role, (group, field) in FIELDS.items():
        item = bindings[role]
        relative = item.get('path') if isinstance(item, dict) else None
        digest = item.get('sha256') if isinstance(item, dict) else None
        if (not isinstance(relative, str) or not relative or
                Path(relative).is_absolute() or '..' in Path(relative).parts or
                not isinstance(digest, str) or len(digest) != 64):
            raise ValueError('unsafe or unversioned original source: ' + role)
        path = packet_path.parent / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(packet_path.parent):
            raise ValueError('original source unavailable: ' + role)
        if sha(path) != digest:
            raise ValueError('original source bytes changed: ' + role)
        expected = site[group][field] if group else site[field]
        if expected != digest:
            raise ValueError('site/source binding differs: ' + role)
        paths[role] = path
    if paths['map'].suffix.lower() != '.xodr':
        raise ValueError('reviewed OpenDRIVE map source required')
    return {'packet': packet, 'site': site, 'paths': paths, 'packet_sha256': sha(packet_path)}
