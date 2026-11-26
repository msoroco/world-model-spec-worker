"""Verify independent site and equipment sources before Native lamp capture."""

import hashlib
import json
from pathlib import Path

from lamp_direction import CASES, validate_scene


ASSIGNMENT = 'testing__C230294__NRS-484D-100-1__motor_vehicle_driver'
SOURCE_FIELDS = ('map_sha256', 'jurisdiction', 'highway', 'vehicle_class', 'parking_status',
                 'required_lamp_provisions', 'device_authority',
                 'device_geometry', 'device_message', 'device_timing',
                 'route', 'sunset_sunrise', 'clock', 'visibility')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(packet_path, case_name):
    """Require a distinct, hash-bound original source for every scene assertion.

    The packet is an operator review artifact, not a legal finding. A file can
    establish a provenance link; a later human audit still checks its truth.
    """
    if case_name not in {case.name for case in CASES}:
        raise ValueError('unknown exact lamp case')
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    if packet.get('case_id') != ASSIGNMENT + '__' + case_name:
        raise ValueError('lamp source packet case mismatch')
    scene = packet.get('scene')
    if not isinstance(scene, dict):
        raise ValueError('lamp source packet scene missing')
    sources = packet.get('sources')
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_FIELDS):
        raise ValueError('complete lamp source inventory missing')
    root = packet_path.parent
    for field in SOURCE_FIELDS:
        entry = sources[field]
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            raise ValueError('lamp source entry missing: ' + field)
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('lamp source file missing: ' + field)
        data = path.read_bytes()
        expected = entry.get('sha256')
        if not isinstance(expected, str) or digest(data) != expected:
            raise ValueError('lamp source bytes changed: ' + field)
        document = json.loads(data)
        if not isinstance(document, dict) or field not in document:
            raise ValueError('lamp source assertion missing: ' + field)
        if scene.get(field) is None:
            raise ValueError('lamp scene assertion missing: ' + field)
        if document[field] != scene.get(field):
            raise ValueError('lamp scene differs from source: ' + field)
        if scene.get(field + '_source_sha256') != expected:
            raise ValueError('lamp scene source seal differs: ' + field)
    case = next(case for case in CASES if case.name == case_name)
    validate_scene(scene, case)
    return {'packet': packet, 'case': case,
            'packet_sha256': digest(packet_path.read_bytes()),
            'source_sha256': {field: sources[field]['sha256'] for field in SOURCE_FIELDS}}
