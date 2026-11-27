"""Reject unsourced highway, curb, route and authority packets before CARLA starts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking import CASES, validate_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path: Path, case_id: str):
    path = Path(path).resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError('reviewed original parking packet missing')
    packet = json.loads(path.read_text(encoding='utf-8'))
    case = next((item for item in CASES if case_id.endswith('__' + item.case_id)), None)
    if case is None or packet.get('case_id') != case_id:
        raise ValueError('reviewed packet exact case mismatch')
    if (packet.get('review_status') != 'reviewed_original_source' or
            packet.get('diagnostic_fixture') is not False or
            not packet.get('reviewer') or not packet.get('review_method')):
        raise ValueError('reviewed original site provenance missing')
    sources = packet.get('sources')
    required = {'map', 'highway', 'edge', 'route', 'ego_blueprint',
                'edge_blueprint', 'authority'}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError('reviewed parking source inventory incomplete')
    for name, source in sources.items():
        if not isinstance(source, dict) or not source.get('path') or not source.get('sha256'):
            raise ValueError('reviewed source identity missing: ' + name)
        target = (path.parent / source['path']).resolve()
        if (not target.is_relative_to(path.parent) or not target.is_file() or
                target.is_symlink() or sha(target) != source['sha256']):
            raise ValueError('reviewed source changed: ' + name)
    map_record = json.loads((path.parent / sources['map']['path']).read_text())
    if (packet.get('map_id') != map_record.get('map_id') or
            len(map_record.get('opendrive_sha256', '')) != 64):
        raise ValueError('reviewed map identity missing')
    site = packet.get('site')
    if not isinstance(site, dict):
        raise ValueError('reviewed parking site absent')
    validate_site(site)
    for field, source in (
        ('map_source_sha256', 'map'), ('highway_source_sha256', 'highway'),
        ('edge_source_sha256', 'edge'), ('approach_route_source_sha256', 'route'),
        ('ego_blueprint_source_sha256', 'ego_blueprint'),
        ('edge_blueprint_source_sha256', 'edge_blueprint')):
        if site[field] != sources[source]['sha256']:
            raise ValueError('reviewed site does not bind source bytes: ' + field)
    for name in ('ego_blueprint_id', 'edge_blueprint_id'):
        if not packet.get(name, '').startswith('vehicle.'):
            raise ValueError('motor vehicle blueprint missing: ' + name)
    if case.exception_probe and not packet.get('authority_record_id'):
        raise ValueError('original exception authority record missing')
    return packet, case
