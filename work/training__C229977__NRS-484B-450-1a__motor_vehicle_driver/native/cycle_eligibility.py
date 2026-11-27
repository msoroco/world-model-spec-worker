"""Source-bound subsection-3 actor eligibility for this exact motor-vehicle cell."""
import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'training__C229977__NRS-484B-450-1a__motor_vehicle_driver'
CLASSES = ('bicycle', 'electric bicycle', 'electric scooter')
LAW_SENTENCE = ('A person may park a bicycle, an electric bicycle or an electric scooter '
                'on a sidewalk provided that the bicycle, electric bicycle or electric scooter '
                'does not impede the normal and reasonable movement of pedestrians on the sidewalk.')


def check(assignment_path, expected_sha256, case_ids):
    path = Path(assignment_path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('Frozen actor/law source hash differs')
    source = json.loads(path.read_text())
    if source.get('assignment_id') != ASSIGNMENT or source.get('actor') != 'motor_vehicle_driver':
        raise ValueError('Wrong frozen actor binding')
    if LAW_SENTENCE not in source.get('law', {}).get('text', ''):
        raise ValueError('Subsection-3 source text missing')
    if not case_ids or any(not case.startswith(ASSIGNMENT + '__') for case in case_ids):
        raise ValueError('Cycle exclusion must map to exact motor-vehicle cases')
    return {'source_sha256': expected_sha256, 'actor': source['actor'],
            'eligible_subsection_3_classes': [], 'source_named_classes': list(CLASSES),
            'case_ids': list(case_ids), 'scope': 'negative actor eligibility only',
            'cycle_branch_runnable_here': False, 'legal_outcome': None}
