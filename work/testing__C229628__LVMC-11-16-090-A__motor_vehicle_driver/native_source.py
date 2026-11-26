"""Validate a reviewed Native site and independent episode sources before capture."""
import hashlib
import json
from pathlib import Path

from contest_aid import CASES, SOURCE_FIELDS, validate_scene

AID = 'testing__C229628__LVMC-11-16-090-A__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read_site(path, case_id):
    path = Path(path).resolve()
    packet = json.loads(path.read_text(encoding='utf-8'))
    case = next((item for item in CASES if case_id == AID + '__' + item.name), None)
    if case is None or packet.get('assignment_id') != AID or packet.get('case_id') != case_id:
        raise ValueError('exact reviewed site and case required')
    if packet.get('source_kind') != 'reviewed_original_native_site':
        raise ValueError('original Native site designation required')
    if packet.get('map_name') is None or packet.get('rate_hz') != 20 or packet.get('duration_frames') != 900:
        raise ValueError('Native map and capture profile required')
    if tuple(packet.get('cameras', ())) != CAMERAS:
        raise ValueError('four original cameras required')
    refs = packet.get('source_refs')
    if not isinstance(refs, list):
        raise ValueError('independent source references required')
    roles = {}
    for ref in refs:
        role = ref.get('role')
        if role in roles:
            raise ValueError('duplicate source role: ' + str(role))
        target = (path.parent / ref.get('path', '')).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file():
            raise ValueError('source outside reviewed site: ' + str(role))
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != ref.get('sha256'):
            raise ValueError('source hash changed: ' + str(role))
        roles[role] = digest
    missing = (set(SOURCE_FIELDS) | {'map'}) - roles.keys()
    if missing:
        raise ValueError('independent source missing: ' + ','.join(sorted(missing)))
    if packet.get('map_sha256') != roles['map']:
        raise ValueError('Native map source hash differs')
    scene = packet.get('scene')
    if not isinstance(scene, dict):
        raise ValueError('reviewed scene missing')
    for role in SOURCE_FIELDS:
        if scene.get(role + '_source_sha256') != roles[role]:
            raise ValueError('scene source differs: ' + role)
    validate_scene(scene, case)
    packet['site_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return packet, scene, case
