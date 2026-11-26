"""Require original authority records before evaluating sidewalk-stop exceptions.

This module checks source bindings only. It never decides whether a law or device
legally authorizes the stop; that determination requires independent review.
"""
import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'training__C229977__NRS-484B-450-1a__motor_vehicle_driver'
KINDS = {'governing_law': 'law', 'official_device': 'device'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def within(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Authority source path must be relative')
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original authority source: ' + relative)
    return path


def check(packet, root, case_id):
    if not isinstance(packet, dict) or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('Wrong authority case identity')
    suffix = case_id.split('__')[-1]
    kind, state = suffix.rsplit('_', 1)
    if kind not in KINDS or state not in ('absent', 'present'):
        raise ValueError('Unsupported authority comparison case')
    if packet.get('case_id') != case_id or packet.get('authority_kind') != KINDS[kind]:
        raise ValueError('Authority packet binds another case or kind')
    if packet.get('legal_conclusion') is not None or packet.get('compliance_independently_verified') is True:
        raise ValueError('Unreviewed authority packet preclaims legal conclusion')
    sources = packet.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('Missing authority source inventory')
    required = {'vehicle-trace.jsonl', 'video_frames.jsonl', 'authority-context.json'}
    if kind == 'official_device':
        required.add('device-trace.jsonl')
    if not required <= set(sources):
        raise ValueError('Missing required original authority source')
    for name, checksum in sources.items():
        if not isinstance(checksum, str) or len(checksum) != 64 or sha(within(root, name)) != checksum:
            raise ValueError('Original authority source hash differs: ' + name)
    binding = packet.get('authority_binding')
    if state == 'absent':
        if binding is not None:
            raise ValueError('Absent case preclaims an authority binding')
    else:
        if not isinstance(binding, dict):
            raise ValueError('Present case lacks exact authority binding')
        if kind == 'governing_law':
            if not all(binding.get(key) for key in ('law_citation', 'law_text_source',
                                                    'law_text_sha256', 'scope_review')):
                raise ValueError('Present case lacks specific governing law source')
            path = within(root, binding['law_text_source'])
            if sha(path) != binding['law_text_sha256']:
                raise ValueError('Governing law source hash differs')
        else:
            if not all(binding.get(key) for key in ('device_actor_id',
                                                    'official_status_source',
                                                    'direction_source', 'effective_interval_source')):
                raise ValueError('Present case lacks original device authority and direction')
            for key in ('official_status_source', 'direction_source',
                        'effective_interval_source'):
                within(root, binding[key])
    return {'case_id': case_id, 'source_bound': True,
            'authority_binding_present': state == 'present',
            'legal_conclusion': None}


def load_and_check(path, root, case_id):
    return check(json.loads(Path(path).read_text()), root, case_id)
