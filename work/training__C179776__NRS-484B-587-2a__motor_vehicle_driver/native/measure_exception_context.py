"""Source-bound 587(2)(a) exception observations; no legal verdict."""

import hashlib
import json
from pathlib import Path


CLASSES = (
    'authorized_emergency_vehicle', 'permitted_emergency_vehicle',
    'traffic_incident_management_vehicle', 'tow_car', 'coroner_vehicle',
    'public_transit_motor_bus',
)
REQUIRED = ('designation.json', 'authority.json', 'sign.json', 'status.json', 'frames.jsonl')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(folder):
    folder = Path(folder)
    index = json.loads((folder / 'sources.json').read_text())
    if index.get('format') != 'c179776-source-bound-exception-context-v1':
        raise ValueError('Context source format differs')
    hashes = index.get('sha256', {})
    if set(hashes) != set(REQUIRED):
        raise ValueError('Required exception source inventory missing')
    for name in REQUIRED:
        if digest(folder / name) != hashes[name]:
            raise ValueError('Exception source hash differs: ' + name)
    sources = {name: json.loads((folder / name).read_text()) for name in REQUIRED[:-1]}
    rows = [json.loads(line) for line in (folder / 'frames.jsonl').read_text().splitlines()]
    designation = sources['designation.json']
    authority = sources['authority.json']
    sign = sources['sign.json']
    status = sources['status.json']
    if (designation.get('controlled_access_highway') is not True or
            not designation.get('public_authority_source') or
            not designation.get('highway_boundary_source') or
            not designation.get('access_restriction_source')):
        raise ValueError('Controlled-access designation authority missing')
    if (authority.get('ego_vehicle_class') not in ('ordinary_motor_vehicle',) + CLASSES or
            not authority.get('vehicle_class_source') or not authority.get('driver_identity_source')):
        raise ValueError('Vehicle class or driver source missing')
    if (sign.get('shoulder_use_allowed') not in (True, False) or
            not isinstance(sign.get('allowed_vehicle_classes'), list) or
            any(value not in CLASSES for value in sign['allowed_vehicle_classes']) or
            not sign.get('permitted_manner_source') or
            not sign.get('placement_authority_source') or
            not sign.get('posted_message_source') or
            not sign.get('physical_sign_source')):
        raise ValueError('Lawfully placed shoulder sign source missing')
    if status.get('subsection_3_claim') not in ('none', 'unresolved'):
        raise ValueError('Subsection 3 status requires separate legal review')
    if len(rows) != 600:
        raise ValueError('Expected 600 original-source frames')
    observed = []
    for i, row in enumerate(rows):
        if (row.get('frame') != 1000 + i or
                abs(row.get('time_s', -999) - i / 20) > 1e-8 or
                row.get('outside_marked_lane') not in (True, False) or
                row.get('fully_paved_shoulder') not in (True, False) or
                row.get('emergency_required') not in (True, False) or
                not row.get('footprint_source') or
                not row.get('emergency_event_source')):
            raise ValueError('Original frame or required temporal source missing')
        if row['fully_paved_shoulder'] and not row['outside_marked_lane']:
            raise ValueError('Shoulder and marked-lane footprint conflict')
        signed_class = (authority['ego_vehicle_class'] in CLASSES and
                        authority['ego_vehicle_class'] in sign['allowed_vehicle_classes'] and
                        row['fully_paved_shoulder'] and sign['shoulder_use_allowed'])
        observed.append({
            'frame': row['frame'],
            'outside_marked_lane': row['outside_marked_lane'],
            'emergency_required': row['emergency_required'],
            'signed_class_shoulder_condition': bool(signed_class),
            'requires_independent_legal_review': row['outside_marked_lane'],
        })
    return {
        'format': 'c179776-exception-observations-v1',
        'source_sha256': hashes,
        'frame_count': len(observed),
        'outside_frames': sum(x['outside_marked_lane'] for x in observed),
        'emergency_outside_frames': sum(x['outside_marked_lane'] and x['emergency_required'] for x in observed),
        'signed_class_shoulder_frames': sum(x['signed_class_shoulder_condition'] for x in observed),
        'subsection_3_claim': status['subsection_3_claim'],
        'physical_original_verified': False,
        'legal_verdict': None,
    }
