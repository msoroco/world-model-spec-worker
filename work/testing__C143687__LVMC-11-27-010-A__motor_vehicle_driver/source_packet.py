"""Verify original administrative and sign records before trail construction.

The packet is a local source inventory. It cannot make a City designation,
dedication or sign legally sufficient; it binds asserted observations to bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


RECORDS = {
    'official_plan_designation': ('administrative_records', 'official_plan_designation', 'source_sha256'),
    'city_trail_dedication': ('administrative_records', 'city_trail_dedication', 'source_sha256'),
    'sign_face': ('sign', 'face_readback_sha256'),
    'governed_access': ('sign', 'governed_access_sha256'),
    'vehicle_class': ('vehicle_class_source_sha256',),
    'operator': ('operator_source_sha256',),
    'exception_status': ('exception_status_source_sha256',),
}


def _get(site, key):
    path = RECORDS[key]
    value = site
    for part in path:
        value = value[part]
    return value


def verify_packet(site: dict, packet_path: Path) -> dict:
    """Return hashes only after each site claim joins an original source file."""
    root = packet_path.resolve().parent
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if packet.get('cell_id') != 'C143687' or packet.get('layout') != 'nonmotorized_trail':
        raise ValueError('source packet cell mismatch')
    sources = packet.get('sources')
    if not isinstance(sources, dict) or set(sources) != set(RECORDS):
        raise ValueError('source packet record inventory incomplete')
    result = {}
    for key in RECORDS:
        entry = sources[key]
        relative = entry.get('path')
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError(f'{key} invalid source path')
        source = (root / relative).resolve()
        if root not in source.parents or not source.is_file():
            raise ValueError(f'{key} source outside packet or missing')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != entry.get('sha256') or digest != _get(site, key):
            raise ValueError(f'{key} source hash mismatch')
        result[key] = digest
    assertions = packet.get('assertions', {})
    for key in ('official_plan_designation', 'city_trail_dedication'):
        actual = site['administrative_records'][key]['asserted']
        if type(assertions.get(key)) is not bool or assertions[key] is not actual:
            raise ValueError(f'{key} source assertion mismatch')
    sign = site['sign']
    if assertions.get('sign_face_text') != sign['face_text'] or (
        type(assertions.get('prohibits_motor_vehicles')) is not bool or
        assertions['prohibits_motor_vehicles'] is not sign['prohibits_motor_vehicles']
    ):
        raise ValueError('sign face source assertion mismatch')
    for key in ('emergency_use', 'maintenance_use'):
        if type(assertions.get(key)) is not bool or assertions[key] is not site[key]:
            raise ValueError(f'{key} source assertion mismatch')
    return {'cell_id': 'C143687', 'packet_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            'source_sha256': result, 'legal_judgment': None}
