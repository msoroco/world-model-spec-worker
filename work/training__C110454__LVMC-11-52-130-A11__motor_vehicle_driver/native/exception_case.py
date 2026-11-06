"""Saved exception context gate for unselected LVMC alternatives.

This tests source continuity, never statutory applicability or physical causation.
"""
import hashlib
import json
from pathlib import Path
from exception_evidence import inspect as inspect_present

CITED_DEVICE_LAW_ID='NRS-484B-300-1'
CITED_DEVICE_LAW_SHA256='0083bdf940bab787cf1d1cf789a93d1edf516df1df6de3b3e91cca237c6bbba8'

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
        if branch == 'compliance_with_law' and (packet.get('cited_law_id') != CITED_DEVICE_LAW_ID or
                packet.get('cited_law_text_sha256') != CITED_DEVICE_LAW_SHA256):
            raise ValueError('Cited law differs from frozen NRS 484B.300(1) source')
        if branch == 'police_or_device_direction':
            video=path.parent/'parking.mkv'
            if not video.is_file() or hashlib.sha256(video.read_bytes()).hexdigest() != packet.get('original_pixel_sha256'):
                raise ValueError('Direction original video hash differs')
        if branch == 'necessary_traffic_conflict':
            actor_source=path.parent/'other_actor_history.jsonl'
            if not actor_source.is_file():
                raise ValueError('Missing required source: other_actor_history.jsonl')
            actor_rows=[json.loads(line) for line in actor_source.read_text().splitlines() if line.strip()]
            if len(actor_rows)!=len(original_frames) or [r.get('native_frame') for r in actor_rows]!=original_frames:
                raise ValueError('Other actor original frame join differs')
            active={index for index,r in enumerate(actor_rows) if r.get('conflict_occupancy') is True}
            if not active.intersection(packet.get('other_actor_frames',[])):
                raise ValueError('Conflict source does not match original actor history')
        source = inspect_present(path, digest, branch)
        return {'source': source, 'requested_polarity': polarity,
                'source_sha256': digest, 'physical_observation_claimed': False}
    if packet.get('observed_exception_source_ids') != []:
        raise ValueError('Absent exception inventory contains a source')
    return {'branch': branch, 'requested_polarity': polarity,
            'source_sha256': digest, 'inventory_frames': len(original_frames),
            'applicability': 'requires_independent_review',
            'physical_observation_claimed': False, 'legal_exception_verdict': None}
