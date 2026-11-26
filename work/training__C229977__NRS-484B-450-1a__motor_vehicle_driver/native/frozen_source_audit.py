"""Report only authority text actually supplied in the frozen assignment."""
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
ASSIGNMENT = 'training__C229977__NRS-484B-450-1a__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    root = REPO / 'inputs' / ASSIGNMENT
    assignment = root / 'assignment.json'
    witnesses = root / 'witnesses.json'
    data = json.loads(assignment.read_text())
    law = data['law']
    if law['id'] != 'NRS-484B-450-1a' or data['actor'] != 'motor_vehicle_driver':
        raise ValueError('Frozen actor or law changed')
    if data['cell']['control'] != 'sidewalk':
        raise ValueError('Frozen sidewalk cell changed')
    if data['local_snapshot']['memberships'].get('full-train'):
        raise ValueError('Frozen membership inventory changed')
    return {'format': 'c229977-frozen-authority-inventory-v1',
            'assignment_id': ASSIGNMENT,
            'assignment_sha256': sha(assignment),
            'witnesses_sha256': sha(witnesses),
            'source_law_id': law['id'], 'source_law_sha256': sha_text(law['text']),
            'source_law_contains_exception_phrase': 'in compliance with law' in law['text'],
            'separate_authorizing_law_source': None,
            'accepted_original_recording_ids': [],
            'governing_law_present_selected': False,
            'legal_conclusion': None}


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
