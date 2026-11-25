"""CPU diagnostic proof for four distinct qualifier source packets."""
import hashlib
import json
from pathlib import Path
import shutil

from qualifier_source_audit import ASSIGNMENT, QUALIFIERS, SOURCE_ROLES, audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / '.runtime-work/c229397-saved-attempt-controlled_2-v2'
    attempt = ROOT / '.runtime-work/c229397-qualifier-source-diagnostic-v3'
    if attempt.exists():
        raise ValueError('Retain existing qualifier diagnostic')
    shutil.copytree(source, attempt)
    folder = attempt / 'qualifier_sources'
    folder.mkdir()
    common = {'vehicle_poses': 'vehicle-poses.jsonl',
              'frame_map': 'video_frames.jsonl',
              'overview_video': 'overview.mkv'}
    frames = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    traffic_path = attempt / 'traffic-actors.jsonl'
    traffic_path.write_text(''.join(json.dumps({
        'video_frame': index, 'native_frame': frame['native_frame'],
        'actor_id': 22, 'speed_mps': 1.0}) + '\n' for index, frame in enumerate(frames)))
    device_path = attempt / 'device-states.jsonl'
    device_path.write_text(''.join(json.dumps({
        'video_frame': index, 'native_frame': frame['native_frame'],
        'device_present': False, 'device_id': None, 'state': None}) + '\n'
        for index, frame in enumerate(frames)))
    context_path = attempt / 'qualifier-context.json'
    context_path.write_text(json.dumps({'device_actor_found': False,
        'authority_and_necessity_unresolved': True}) + '\n')
    reports = {}
    for qualifier in QUALIFIERS:
        sources = {role: {'path': name, 'sha256': sha(attempt / name)}
                   for role, name in common.items()}
        for role in SOURCE_ROLES[qualifier]:
            if qualifier == 'traffic_conflict' and role == 'participant_motion':
                path = traffic_path
            elif qualifier == 'device_direction' and role == 'device_identity':
                path = context_path
            elif qualifier == 'device_direction' and role == 'device_state':
                path = device_path
            else:
                path = folder / (qualifier + '-' + role + '.txt')
                path.write_text('Synthetic diagnostic source role: ' + qualifier + ' / ' + role + '\n')
            sources[role] = {'path': str(path.relative_to(attempt)), 'sha256': sha(path)}
        packet = {'format': 'c229397-qualifier-source-packet-v1',
                  'case_suffix': 'controlled_2', 'qualifier': qualifier,
                  'finding': 'unresolved', 'diagnostic_fixture': True,
                  'source_kind': 'synthetic_fixture', 'sources': sources,
                  'reviewed_video_frames': [200, 300]}
        path = folder / (qualifier + '-packet.json')
        path.write_text(json.dumps(packet, indent=2) + '\n')
        case = ASSIGNMENT + '__controlled_2'
        result = audit(attempt, path, case, qualifier, diagnostic=True)
        if result['finding'] != 'unresolved' or result['legal_verdict'] is not None:
            raise ValueError('Diagnostic qualifier reached a legal result')
        try:
            audit(attempt, path, case, qualifier, diagnostic=False)
        except ValueError:
            pass
        else:
            raise ValueError('Synthetic qualifier source passed original-mode audit')
        stale = json.loads(path.read_text())
        stale['sources'][SOURCE_ROLES[qualifier][0]]['sha256'] = '0' * 64
        stale_path = folder / (qualifier + '-stale.json')
        stale_path.write_text(json.dumps(stale, indent=2) + '\n')
        try:
            audit(attempt, stale_path, case, qualifier, diagnostic=True)
        except ValueError as error:
            if str(error) != 'Qualifier source missing or stale: ' + SOURCE_ROLES[qualifier][0]:
                raise
        else:
            raise ValueError('Stale qualifier source was accepted')
        reports[qualifier] = {'packet_sha256': sha(path), 'finding': result['finding'],
                              'positive': True, 'stale_source_rejected': True,
                              'original_mode_rejected_synthetic': True}
    print(json.dumps({'passed': True, 'diagnostic_fixture': True,
                      'case_id': ASSIGNMENT + '__controlled_2',
                      'qualifiers': reports, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
