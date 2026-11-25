"""Bind distinct statutory qualifier reviews to exact saved sources.

This reports review provenance and explicit unresolved findings. It does not
infer necessity, legal compliance, direction authority, or a legal verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = 'training__C229397__LVMC-11-52-130-A12__motor_vehicle_driver'
QUALIFIERS = ('traffic_conflict', 'law_compliance', 'police_direction', 'device_direction')
SOURCE_ROLES = {
    'traffic_conflict': ('participant_motion', 'traffic_context_review'),
    'law_compliance': ('applicable_law_text', 'law_context_review', 'authority_timeline'),
    'police_direction': ('officer_identity', 'officer_direction',
                         'direction_context_review', 'authority_timeline'),
    'device_direction': ('device_identity', 'device_state', 'direction_context_review'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, packet_path, case_id, qualifier, diagnostic=False):
    attempt = Path(attempt).resolve()
    packet = json.loads(Path(packet_path).read_text())
    if case_id != ASSIGNMENT + '__' + packet.get('case_suffix', '') or qualifier not in QUALIFIERS:
        raise ValueError('Exact qualifier case identity differs')
    if packet.get('format') != 'c229397-qualifier-source-packet-v1' or packet.get('qualifier') != qualifier:
        raise ValueError('Qualifier source packet identity differs')
    if packet.get('finding') not in ('present', 'absent', 'unresolved'):
        raise ValueError('Qualifier finding must remain explicit')
    if packet.get('diagnostic_fixture') is not diagnostic:
        raise ValueError('Qualifier packet provenance differs')
    if not diagnostic:
        from worker_exchange.native_output import provenance_record

        provenance = provenance_record(attempt)
        seal = attempt / 'capture-seal.json'
        if (packet.get('source_kind') != 'original_native' or
                provenance['provenance_kind'] != 'native' or
                provenance['diagnostic_fixture'] is not False or
                not seal.is_file() or
                packet.get('capture_seal_sha256') != sha(seal)):
            raise ValueError('Original Native qualifier source required')
    sources = packet.get('sources', {})
    if set(sources) != set(SOURCE_ROLES[qualifier]) | {'vehicle_poses', 'frame_map', 'overview_video'}:
        raise ValueError('Qualifier lacks exact source roles')
    bound = {}
    for role, ref in sources.items():
        rel = ref.get('path') if isinstance(ref, dict) else None
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('Invalid qualifier source path: ' + role)
        path = (attempt / rel).resolve()
        if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != ref.get('sha256'):
            raise ValueError('Qualifier source missing or stale: ' + role)
        bound[role] = ref['sha256']
    expected = {'vehicle_poses': 'vehicle-poses.jsonl', 'frame_map': 'video_frames.jsonl',
                'overview_video': 'overview.mkv'}
    if any(sources[role]['path'] != name for role, name in expected.items()):
        raise ValueError('Qualifier original frame or video source differs')
    for role in SOURCE_ROLES[qualifier]:
        if not (attempt / sources[role]['path']).stat().st_size:
            raise ValueError('Qualifier role source empty: ' + role)
    if qualifier == 'traffic_conflict' and sources['participant_motion']['path'] != 'traffic-actors.jsonl':
        raise ValueError('Traffic context must use Native second actor motion')
    if qualifier == 'device_direction' and (
            sources['device_identity']['path'] != 'qualifier-context.json' or
            sources['device_state']['path'] != 'device-states.jsonl'):
        raise ValueError('Device context must use Native identity and state')
    if qualifier in ('law_compliance', 'police_direction') and (
            sources['authority_timeline']['path'] != 'authority-events.jsonl'):
        raise ValueError('Authority context must use Native frame timeline')
    poses = [json.loads(row) for row in (attempt / 'vehicle-poses.jsonl').read_text().splitlines()]
    frames = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(poses) != len(frames) or len(frames) != 600 or any(
            pose.get('video_frame') != frame.get('video_frame') or
            pose.get('native_frame') != frame.get('native_frame')
            for pose, frame in zip(poses, frames)):
        raise ValueError('Qualifier original frame join incomplete')
    if qualifier in ('traffic_conflict', 'device_direction', 'law_compliance',
                     'police_direction'):
        role = ('participant_motion' if qualifier == 'traffic_conflict'
                else 'device_state' if qualifier == 'device_direction'
                else 'authority_timeline')
        rows = [json.loads(row) for row in (attempt / sources[role]['path']).read_text().splitlines()]
        if len(rows) != 600 or any(
                row.get('video_frame') != index or row.get('native_frame') != frames[index]['native_frame']
                for index, row in enumerate(rows)):
            raise ValueError('Qualifier Native context/frame join incomplete')
        if qualifier == 'traffic_conflict' and len({row.get('actor_id') for row in rows}) != 1:
            raise ValueError('Traffic context actor identity differs across frames')
        if qualifier == 'device_direction' and packet['finding'] == 'present' and not all(
                row.get('device_present') and row.get('device_id') is not None for row in rows):
            raise ValueError('Device presence finding lacks Native device state')
        if qualifier == 'police_direction' and len({row.get('candidate_participant_id')
                for row in rows}) != 1:
            raise ValueError('Direction participant identity differs across frames')
    observed = packet.get('reviewed_video_frames')
    if not isinstance(observed, list) or not observed or any(
            not isinstance(i, int) or i < 0 or i >= 600 for i in observed):
        raise ValueError('Qualifier review lacks bounded original frames')
    return {'format': 'c229397-qualifier-source-audit-v1', 'case_id': case_id,
            'qualifier': qualifier, 'finding': packet['finding'],
            'diagnostic_fixture': diagnostic, 'source_hashes': bound,
            'reviewed_video_frames': observed, 'source_frame_count': 600,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--qualifier', choices=QUALIFIERS, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.packet, args.case, args.qualifier, args.diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
