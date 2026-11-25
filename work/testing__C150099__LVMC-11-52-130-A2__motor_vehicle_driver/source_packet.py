"""Validate original site evidence before constructing a fire-lane case.

The packet must be supplied by local review. A diagnostic fixture can exercise
this validator, but cannot establish a City Fire Code designation or posting.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fire_lane import CASES, validate_site

SOURCES = (
    'map', 'jurisdiction', 'fire_code_designation', 'posting_authority',
    'posted_extent', 'sign_identity', 'sign_appearance', 'curb_geometry',
    'property_source', 'one_way_source', 'ego_blueprint', 'camera_plan',
    'route', 'weather',
)
EXCEPTION_SOURCES = {
    'lawful_traffic_conflict': 'traffic_conflict_source',
    'police_direction': 'police_direction_source',
    'traffic_device_direction': 'traffic_device_source',
}


def _source(packet: dict, name: str, base: Path) -> str:
    entry = packet.get('sources', {}).get(name)
    if not isinstance(entry, dict) or not entry.get('path') or not entry.get('sha256'):
        raise ValueError('original source missing: ' + name)
    path = Path(entry['path'])
    if not path.is_absolute():
        path = base / path
    if not path.is_file():
        raise ValueError('original source file missing: ' + name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != entry['sha256']:
        raise ValueError('original source hash changed: ' + name)
    if name in ('fire_code_designation', 'posting_authority', 'jurisdiction'):
        if not entry.get('reviewer') or not entry.get('citation'):
            raise ValueError('official source review missing: ' + name)
    return digest


def validate_packet(path: Path, case_id: str) -> dict:
    """Return a source-bound site only after exact, location-specific review.

    No string label or empty metadata is accepted as proof of an official act.
    Physical visibility is a separate later original-video check.
    """
    path = Path(path)
    packet = json.loads(path.read_text(encoding='utf-8'))
    matches = [case for case in CASES if case_id.endswith('__' + case.id)]
    if len(matches) != 1 or packet.get('case_id') != case_id:
        raise ValueError('source packet case identity mismatch')
    if packet.get('source_kind') != 'reviewed_original_site' or not packet.get('reviewer'):
        raise ValueError('reviewed original site required')
    case = matches[0]
    site = dict(packet.get('site') or {})
    for name in SOURCES:
        site[name + '_sha256'] = _source(packet, name, path.parent)
    if case.exception != 'none':
        name = EXCEPTION_SOURCES[case.exception]
        site[name + '_sha256'] = _source(packet, name, path.parent)
    validate_site(site, case)
    if site.get('sign_support') == 'spawned_prop' and not packet.get('sign_prop_provenance'):
        raise ValueError('spawned sign provenance missing')
    return site
