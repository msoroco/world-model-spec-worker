"""Verify reviewed source bytes before constructing the grade-standing scene.

The packet is supplied by the local operator. A worker fixture may exercise this
validator, but it is never a reviewed site or an original vehicle observation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from grade_stand import CASES, validate_scene


ASSIGNMENT = 'testing__C276300__NRS-484B-533__motor_vehicle_driver'
SOURCE_FIELDS = (
    'map_opendrive', 'highway', 'vehicle', 'grade', 'curb_side', 'engine', 'brake_mechanics',
    'front_wheels', 'responsible_person', 'person_actions',
    'standing_interval', 'passenger_activity', 'other_vehicle_route',
)


def verify(path: Path, *, diagnostic_fixture: bool = False) -> dict:
    path = Path(path).resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError('reviewed grade-standing packet missing')
    packet = json.loads(path.read_text())
    case_id = packet.get('case_id')
    case = next((item for item in CASES
                 if case_id == ASSIGNMENT + '__' + item.name), None)
    if case is None or packet.get('assignment_id') != ASSIGNMENT:
        raise ValueError('grade-standing packet selects another exact case')
    if packet.get('source_kind') != ('diagnostic_fixture' if diagnostic_fixture
                                     else 'reviewed_original'):
        raise ValueError('grade-standing source kind is unreviewed')
    scene = packet.get('scene')
    if not isinstance(scene, dict):
        raise ValueError('grade-standing scene missing')
    validate_scene(scene, case)
    refs = packet.get('source_refs')
    if not isinstance(refs, dict) or set(refs) != set(SOURCE_FIELDS):
        raise ValueError('grade-standing source inventory incomplete')
    hashes = {}
    for field in SOURCE_FIELDS:
        ref = refs[field]
        if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
            raise ValueError('grade-standing source reference malformed: ' + field)
        name = ref['path']
        source = (path.parent / name).resolve()
        if (Path(name).is_absolute() or source.parent != path.parent or
                source == path or not source.is_file() or source.is_symlink()):
            raise ValueError('grade-standing source file missing: ' + field)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        scene_key = ('map_opendrive_sha256' if field == 'map_opendrive'
                     else field + '_source_sha256')
        if (ref.get('sha256') != digest or scene.get(scene_key) != digest):
            raise ValueError('grade-standing source bytes changed: ' + field)
        hashes[field] = digest
    return {'case_id': case_id, 'case': case, 'scene': scene,
            'source_hashes': hashes, 'source_kind': packet['source_kind']}
