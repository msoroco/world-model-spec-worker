"""Review and seal source bytes before any C150098 Native construction.

This preflight does not infer municipal authority or physical visibility. A
reviewer must supply the original map, hydrant, parking and camera sources.
"""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path

from hydrant import ASSIGNMENT, CASES, validate_site


REQUIRED_SOURCES = {
    'opendrive': 'map_sha256',
    'jurisdiction': 'municipal_jurisdiction_sha256',
    'parallel_parking_authority': 'parallel_parking_authority_sha256',
    'hydrant_identity': 'hydrant_identity_sha256',
    'hydrant_geometry': 'hydrant_geometry_sha256',
    'hydrant_blueprint': 'hydrant_blueprint_sha256',
    'curb': 'curb_source_sha256',
    'one_way_direction': 'one_way_direction_sha256',
    'ego_blueprint': 'ego_blueprint_sha256',
    'camera_plan': 'camera_plan_sha256',
}
EXCEPTION_SOURCE = {
    'lawful_traffic_conflict': ('traffic_conflict', 'traffic_conflict_source_sha256'),
    'police_direction': ('police_direction', 'police_direction_source_sha256'),
    'traffic_device_direction': ('traffic_device', 'traffic_device_source_sha256'),
}
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def _source(root: Path, item, name: str) -> str:
    if not isinstance(item, dict) or not all(item.get(k) for k in
                                             ('path', 'sha256', 'citation', 'reviewer')):
        raise ValueError('reviewed source required: ' + name)
    relative = Path(item['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('source path escapes packet: ' + name)
    target = root / relative
    if target.is_symlink() or not target.is_file() or root not in target.resolve().parents:
        raise ValueError('source bytes missing: ' + name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != item['sha256']:
        raise ValueError('source bytes changed: ' + name)
    return digest


def validate_packet(path, case_id):
    path = Path(path).resolve()
    packet = json.loads(path.read_text(encoding='utf-8'))
    if packet.get('review_status') != 'reviewed' or not packet.get('reviewer'):
        raise ValueError('reviewed original site packet required')
    if packet.get('case_id') != case_id or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('reviewed packet exact case differs')
    matches = [case for case in CASES if ASSIGNMENT + '__' + case.suffix == case_id]
    if len(matches) != 1:
        raise ValueError('unknown exact hydrant case')
    case = matches[0]
    planned = packet.get('planned_case')
    if (not isinstance(planned, dict) or planned.get('side') != case.side or
            planned.get('activity') != case.activity or
            planned.get('exception') != case.exception or
            type(planned.get('gap_m')) not in (int, float) or
            abs(planned['gap_m'] - case.gap_m) > 1e-9):
        raise ValueError('reviewed packet exact construction differs')
    site = packet.get('site')
    if not isinstance(site, dict):
        raise ValueError('reviewed site missing')
    validate_site(site)
    sources = packet.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('reviewed source inventory missing')
    required = dict(REQUIRED_SOURCES)
    if case.exception != 'none':
        name, field = EXCEPTION_SOURCE[case.exception]
        required[name] = field
    hashes = {name: _source(path.parent, sources.get(name), name) for name in required}
    for name, field in required.items():
        if site.get(field) != hashes[name]:
            raise ValueError('site source binding differs: ' + name)
    camera_path = path.parent / sources['camera_plan']['path']
    cameras = json.loads(camera_path.read_text(encoding='utf-8'))
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError('four original camera views required')
    for camera, expected in zip(cameras, VIEWS):
        if tuple(camera.get(k) for k in ('name', 'width', 'height')) != expected:
            raise ValueError('original camera profile differs')
        for key in ('location_xyz_m', 'rotation_rpy_deg'):
            values = camera.get(key)
            if (not isinstance(values, list) or len(values) != 3 or
                    any(type(x) not in (int, float) or not isfinite(x) for x in values)):
                raise ValueError('reviewed original camera pose missing')
        if not camera.get('pose_source'):
            raise ValueError('reviewed original camera pose missing')
    return site, case, hashes, cameras
