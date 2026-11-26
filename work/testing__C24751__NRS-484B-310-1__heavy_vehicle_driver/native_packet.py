"""Seal reviewed original sources before C24751 Native construction."""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path

from flashing_red_native import ASSIGNMENT, CASES, reference

VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
SOURCES = {
    'opendrive': 'map_sha256',
    'approach': 'approach_source_sha256',
    'signal_identity': 'signal_identity_sha256',
    'signal_geometry': 'signal_geometry_sha256',
    'signal_blueprint': 'signal_blueprint_sha256',
    'occluder_identity': 'occluder_identity_sha256',
    'occluder_geometry': 'occluder_geometry_sha256',
    'occluder_blueprint': 'occluder_blueprint_sha256',
    'ego_blueprint': 'ego_blueprint_sha256',
    'stop_geometry': 'stop_geometry_sha256',
    'camera_plan': 'camera_plan_sha256',
}


def source_hash(root, item, name):
    if not isinstance(item, dict) or not all(item.get(key) for key in
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
    matches = [case for case in CASES if case_id == ASSIGNMENT + '__' + case.suffix]
    if len(matches) != 1:
        raise ValueError('unknown exact flashing-red case')
    case = matches[0]
    site = packet.get('site')
    if not isinstance(site, dict):
        raise ValueError('reviewed site missing')
    reference(site, case)
    planned = packet.get('planned_case')
    if (not isinstance(planned, dict) or planned.get('reference') != case.reference
            or planned.get('stop_offset_m') != case.stop_offset_m):
        raise ValueError('reviewed packet exact stop construction differs')
    items = packet.get('sources')
    if not isinstance(items, dict):
        raise ValueError('reviewed source inventory missing')
    hashes = {name: source_hash(path.parent, items.get(name), name)
              for name in SOURCES}
    for name, field in SOURCES.items():
        if site.get(field) != hashes[name]:
            raise ValueError('site source binding differs: ' + name)
    cameras = json.loads((path.parent / items['camera_plan']['path']).read_text(encoding='utf-8'))
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError('four original camera views required')
    for camera, expected in zip(cameras, VIEWS):
        if tuple(camera.get(k) for k in ('name', 'width', 'height')) != expected:
            raise ValueError('original camera profile differs')
        for name in ('location_xyz_m', 'rotation_rpy_deg'):
            values = camera.get(name)
            if (not isinstance(values, list) or len(values) != 3
                    or any(type(value) not in (int, float) or not isfinite(value)
                           for value in values)):
                raise ValueError('reviewed original camera pose missing')
        if not camera.get('pose_source'):
            raise ValueError('reviewed original camera pose source missing')
    return site, case, hashes, cameras
