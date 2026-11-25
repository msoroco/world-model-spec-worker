"""Verify a reviewed, source-hashed speed-zone site before Native construction.

The packet is supplied by the local operator. A diagnostic packet can exercise
the parser but cannot establish that a zone or sign exists in the real map.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from speed_zone import CASES, validate_site


REQUIRED = ('road_map', 'public_access', 'road_boundary', 'zone_establishment',
            'zone_extent', 'sign_instruction', 'eastbound_lane', 'westbound_lane',
            'eastbound_sign', 'westbound_sign', 'vehicle_classification')
FIELD = {
    'road_map': 'road_source_sha256',
    'public_access': 'public_access_source_sha256',
    'road_boundary': 'boundary_source_sha256',
    'zone_establishment': 'zone_establishment_source_sha256',
    'zone_extent': 'zone_extent_source_sha256',
    'sign_instruction': 'sign_instruction_source_sha256',
}


def validate_packet(path, selected_case_id):
    path = Path(path).resolve()
    packet = json.loads(path.read_text())
    if packet.get('format') != 'c136559-reviewed-speed-site-v1' or \
            packet.get('cell_id') != 'C136559' or \
            packet.get('law_id') != 'NRS-484B-620-2' or \
            packet.get('actor') != 'motor_vehicle_driver' or \
            packet.get('case_id') != selected_case_id:
        raise ValueError('reviewed speed-site identity mismatch')
    sources = packet.get('sources', {})
    if set(sources) != set(REQUIRED):
        raise ValueError('reviewed speed-site source inventory incomplete')
    for name, entry in sources.items():
        source = Path(entry.get('path', ''))
        if not source.is_absolute():
            source = path.parent / source
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry.get('sha256'):
            raise ValueError('reviewed speed-site source absent or changed: ' + name)
    site = packet.get('site')
    if not isinstance(site, dict):
        raise ValueError('reviewed speed-site geometry absent')
    for name, field in FIELD.items():
        if site.get(field) != sources[name]['sha256']:
            raise ValueError('speed-site source binding mismatch: ' + name)
    for direction in ('eastbound', 'westbound'):
        if site.get('lanes', {}).get(direction, {}).get('source_sha256') != sources[direction + '_lane']['sha256']:
            raise ValueError('directional lane source binding mismatch: ' + direction)
        if site.get('signs', {}).get(direction, {}).get('source_sha256') != sources[direction + '_sign']['sha256']:
            raise ValueError('directional sign source binding mismatch: ' + direction)
    if site.get('vehicle_class_source_sha256') != sources['vehicle_classification']['sha256']:
        raise ValueError('vehicle classification source binding mismatch')
    suffix = selected_case_id.rsplit('__', 1)[-1]
    case = next((item for item in CASES if item.case_id == suffix), None)
    if case is None:
        raise ValueError('unknown exact speed-zone case')
    validate_site(site, case)
    return packet, site, case
