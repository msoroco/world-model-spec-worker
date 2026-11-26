"""Require reviewed original source bytes for one rear-signal Native scene."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rear_signal import validate_scene

TOP = ('jurisdiction', 'one_way_route', 'stop_footprint', 'ego_vehicle',
       'ego_driver_control', 'signal_device', 'rear_visibility',
       'conflict_context', 'official_direction_context')
REAR = ('vehicle', 'driver', 'position', 'motion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_scene(path, case_id):
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding='utf-8'))
    if (scene.get('format') != 'c150640-reviewed-original-rear-signal-v1' or
            scene.get('source_kind') != 'original_reviewed' or
            scene.get('diagnostic_fixture') is not False or
            scene.get('case_id') != case_id or not scene.get('reviewer')):
        raise ValueError('reviewed original rear-signal scene identity missing')
    sources = scene.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('reviewed scene source inventory missing')
    for role in (*TOP, *('rear_' + item for item in REAR), 'map'):
        item = sources.get(role)
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed original source missing: ' + role)
        candidate = path.parent / item['path']
        source = candidate.resolve()
        if candidate.is_symlink() or not source.is_relative_to(path.parent) or not source.is_file():
            raise ValueError('reviewed original source path escapes packet: ' + role)
        if sha(source) != item['sha256']:
            raise ValueError('reviewed original source hash differs: ' + role)
    for role in TOP:
        if scene.get(role + '_source_sha256') != sources[role]['sha256']:
            raise ValueError('reviewed scene source binding differs: ' + role)
    for role in REAR:
        if scene.get('rear_vehicle', {}).get(role + '_source_sha256') != sources['rear_' + role]['sha256']:
            raise ValueError('reviewed rear source binding differs: ' + role)
    if scene.get('map_source_sha256') != sources['map']['sha256']:
        raise ValueError('reviewed map source binding differs')
    if not scene.get('map_id') or not scene.get('ego_blueprint_id') or not scene.get('rear_blueprint_id'):
        raise ValueError('reviewed Native map or vehicle blueprint missing')
    if not scene.get('rear_driver_blueprint_id') and scene['rear_vehicle']['driver_present']:
        raise ValueError('reviewed rear driver blueprint missing')
    validate_scene(scene)
    return scene
