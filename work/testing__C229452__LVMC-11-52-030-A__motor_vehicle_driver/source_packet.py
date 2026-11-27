"""Bind an exact red-curb Native run to reviewed original local sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from red_curb import CASES, validate_scene


ASSIGNMENT = 'testing__C229452__LVMC-11-52-030-A__motor_vehicle_driver'
SOURCE_FIELDS = (
    'jurisdiction', 'red_curb', 'governed_location', 'parking_position',
    'vehicle_classification', 'sign', 'activity', 'purpose', 'attendance',
    'engine', 'traffic_conflict', 'police_direction', 'device_direction',
    'vehicle_status', 'mail_dropbox', 'mail_activity',
)
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_source(root, field, entry, reviewer):
    if not isinstance(entry, dict) or not all(entry.get(key) for key in
                                               ('path', 'sha256', 'citation', 'reviewer')):
        raise ValueError('reviewed original source reference missing: ' + field)
    if entry['reviewer'] != reviewer:
        raise ValueError('reviewer identity changed: ' + field)
    relative = Path(entry['path'])
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('relative original source path required: ' + field)
    path = root / relative
    if not path.is_file() or path.is_symlink() or sha(path) != entry['sha256']:
        raise ValueError('original source bytes missing or changed: ' + field)
    return path


def load_reviewed(path, case_id):
    path = Path(path).resolve(strict=True)
    packet = json.loads(path.read_text(encoding='utf-8'))
    if (packet.get('format') != 'c229452-reviewed-red-curb-v1' or
            packet.get('assignment_id') != ASSIGNMENT or
            not packet.get('reviewer') or not packet.get('review_citation')):
        raise ValueError('exact reviewed red-curb packet required')
    case = next((item for item in CASES if ASSIGNMENT + '__' + item.name == case_id), None)
    if case is None or packet.get('case_id') != case_id:
        raise ValueError('reviewed packet belongs to another case')
    sources = packet.get('sources')
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_FIELDS):
        raise ValueError('every red-curb source required')
    scene = packet.get('scene')
    if not isinstance(scene, dict):
        raise ValueError('reviewed red-curb scene missing')
    for field in SOURCE_FIELDS:
        checked_source(path.parent, field, sources[field], packet['reviewer'])
        if scene.get(field + '_source_sha256') != sources[field]['sha256']:
            raise ValueError('scene source hash changed: ' + field)
    camera_plan = packet.get('camera_plan')
    if (not isinstance(camera_plan, dict) or set(camera_plan) != set(CAMERAS) or
            any(not isinstance(item, dict) or not item.get('source_transform') or
                    not item.get('purpose') for item in camera_plan.values())):
        raise ValueError('reviewed four-camera placement source required')
    validate_scene(scene, case)
    return packet, scene, case


def checked_adapter(path, packet):
    entry = packet.get('native_adapter')
    if not isinstance(entry, dict) or not entry.get('sha256') or not entry.get('citation'):
        raise ValueError('reviewed Native adapter binding missing')
    path = Path(path).resolve(strict=True)
    if path.is_symlink() or sha(path) != entry['sha256']:
        raise ValueError('reviewed Native adapter bytes changed')
    return path
