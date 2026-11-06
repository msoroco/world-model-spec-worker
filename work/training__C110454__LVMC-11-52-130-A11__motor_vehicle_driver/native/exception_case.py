"""Saved exception context gate for unselected LVMC alternatives.

This tests source continuity, never statutory applicability or physical causation.
"""
import hashlib
import json
from pathlib import Path
from exception_evidence import inspect as inspect_present

BRANCHES = {
    'exception_1_1': ('necessary_traffic_conflict', 'absent'),
    'exception_1_2': ('necessary_traffic_conflict', 'present'),
    'exception_2_1': ('compliance_with_law', 'absent'),
    'exception_2_2': ('compliance_with_law', 'present'),
    'exception_3_1': ('police_or_device_direction', 'absent'),
    'exception_3_2': ('police_or_device_direction', 'present'),
}


def inspect_case(path: Path, suffix: str, original_frames: list[int]):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: exception_context.json')
    if suffix not in BRANCHES:
        raise ValueError('Unknown exception case')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    packet = json.loads(path.read_text())
    branch, polarity = BRANCHES[suffix]
    if packet.get('source_kind') != 'native_context_schema' or packet.get('branch') != branch:
        raise ValueError('Exception case source identity differs')
    if packet.get('requested_polarity') != polarity:
        raise ValueError('Exception polarity differs')
    if packet.get('original_frames') != original_frames:
        raise ValueError('Exception context is not joined to all original frames')
    if polarity == 'present':
        source = inspect_present(path, digest, branch)
        return {'source': source, 'requested_polarity': polarity,
                'source_sha256': digest, 'physical_observation_claimed': False}
    if packet.get('observed_exception_source_ids') != []:
        raise ValueError('Absent exception inventory contains a source')
    return {'branch': branch, 'requested_polarity': polarity,
            'source_sha256': digest, 'inventory_frames': len(original_frames),
            'applicability': 'requires_independent_review',
            'physical_observation_claimed': False, 'legal_exception_verdict': None}
