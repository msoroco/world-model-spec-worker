"""Saved exception context gate for unselected LVMC alternatives.

This tests source continuity, never statutory applicability or physical causation.
"""
import hashlib
import json
import math
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
        if branch == 'compliance_with_law':
            action_source=path.parent/'device_action_history.jsonl'
            if not action_source.is_file():
                raise ValueError('Missing required source: device_action_history.jsonl')
            action_rows=[json.loads(line) for line in action_source.read_text().splitlines() if line.strip()]
            if len(action_rows)!=len(original_frames) or [r.get('native_frame') for r in action_rows]!=original_frames:
                raise ValueError('Device action original frame join differs')
            if any(r.get('device_id')!='620' or r.get('device_type')!='206' or
                   r.get('device_road_id')!=2 or isinstance(r.get('ego_speed_mps'),bool) or
                   not isinstance(r.get('ego_speed_mps'),(int,float)) or not math.isfinite(r['ego_speed_mps'])
                   for r in action_rows):
                raise ValueError('Device and ego Native readback differs')
            action_frames={index for index,r in enumerate(action_rows) if r.get('ego_brake_applied') is True}
            if action_frames!=set(packet.get('ego_action_frames',[])):
                raise ValueError('Device ego action source does not match exception context')
            if not action_frames or not all(index>0 and action_rows[index]['ego_speed_mps']<action_rows[index-1]['ego_speed_mps']
                                            for index in action_frames):
                raise ValueError('Device ego action has no measured deceleration')
        if branch == 'police_or_device_direction':
            video=path.parent/'parking.mkv'
            if not video.is_file() or hashlib.sha256(video.read_bytes()).hexdigest() != packet.get('original_pixel_sha256'):
                raise ValueError('Direction original video hash differs')
        if branch == 'necessary_traffic_conflict':
            actor_source=path.parent/'other_actor_history.jsonl'
            ego_source=path.parent/'ego_response_history.jsonl'
            if not actor_source.is_file():
                raise ValueError('Missing required source: other_actor_history.jsonl')
            if not ego_source.is_file():
                raise ValueError('Missing required source: ego_response_history.jsonl')
            actor_rows=[json.loads(line) for line in actor_source.read_text().splitlines() if line.strip()]
            ego_rows=[json.loads(line) for line in ego_source.read_text().splitlines() if line.strip()]
            if len(actor_rows)!=len(original_frames) or [r.get('native_frame') for r in actor_rows]!=original_frames:
                raise ValueError('Other actor original frame join differs')
            if len(ego_rows)!=len(original_frames) or [r.get('native_frame') for r in ego_rows]!=original_frames:
                raise ValueError('Ego response original frame join differs')
            active={index for index,r in enumerate(actor_rows) if r.get('conflict_occupancy') is True}
            if not active.intersection(packet.get('other_actor_frames',[])):
                raise ValueError('Conflict source does not match original actor history')
            braking={index for index,r in enumerate(ego_rows) if r.get('response_onset') is True}
            if braking != set(packet.get('ego_brake_frames',[])) or any(
                ego_rows[index].get('conflict_brake_override') is not True or
                ego_rows[index].get('brake_applied') is not True for index in braking):
                raise ValueError('Ego conflict-brake onset does not match exception context')
            for index,r in enumerate(ego_rows):
                expected_onset=(r.get('conflict_brake_override') is True and
                                (index==0 or ego_rows[index-1].get('conflict_brake_override') is not True))
                if r.get('response_onset') is not expected_onset:
                    raise ValueError('Ego conflict-brake onset differs from override history')
            if not braking or not any(any(abs(a-b)<=1 for a in active) for b in braking):
                raise ValueError('Ego brake does not overlap the source conflict window')
            for index in braking:
                if index==0 or not isinstance(ego_rows[index]['speed_mps'],(int,float)) or not isinstance(ego_rows[index-1]['speed_mps'],(int,float)) or not math.isfinite(ego_rows[index]['speed_mps']) or not math.isfinite(ego_rows[index-1]['speed_mps']) or ego_rows[index]['speed_mps']>=ego_rows[index-1]['speed_mps']:
                    raise ValueError('Ego brake has no measured deceleration')
        source = inspect_present(path, digest, branch)
        return {'source': source, 'requested_polarity': polarity,
                'source_sha256': digest, 'physical_observation_claimed': False}
    if packet.get('observed_exception_source_ids') != []:
        raise ValueError('Absent exception inventory contains a source')
    return {'branch': branch, 'requested_polarity': polarity,
            'source_sha256': digest, 'inventory_frames': len(original_frames),
            'applicability': 'requires_independent_review',
            'physical_observation_claimed': False, 'legal_exception_verdict': None}
