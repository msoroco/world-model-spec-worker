"""Independent saved turn-source audit; synthetic probes make no physical finding."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video

ORIGINALS = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
             'affected_participants.json', 'participant_bodies.jsonl',
             'listener_audio_original.jsonl', 'video_frames.jsonl', 'trace.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(case, attempt, processed, negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    require(entry is not None and entry['kind'] == 'delivery', 'Unknown exact turn case')
    attempt, processed = Path(attempt), Path(processed)
    report = json.loads((processed / 'v0001/analysis/analysis-report.json').read_text())
    receipt = json.loads((HERE / entry['saved_processing']['receipt']).read_text())
    require(report['case_id'] == receipt['case_id'] == case and receipt['passed']
            and receipt['originals_preserved'], 'Wrong saved turn case or originals')
    require(receipt['native_revision']['construction_sha256'] == entry['construction_sha256'],
            'Stale exact construction')
    observed = report['measurements']['turn_signal_observation']
    names = (*ORIGINALS, *VIDEOS)
    if case.endswith(('__pedestrian_horn_before_turn',
                      '__pedestrian_farther_horn_before_turn',
                      '__both_users_both_signals')):
        names += ('horn_actuation.jsonl',)
    hashes = {name: digest(attempt / name) for name in names}
    if negative:
        hashes['listener_audio_original.jsonl'] = '0' * 64
    for name, value in hashes.items():
        require(receipt['original_source_hashes'].get(name) == value,
                'Stale or missing original listener source: ' + name)
    for name, value in observed['sources'].items():
        require(hashes.get(name) == value, 'Stale saved turn observation: ' + name)
    motion = rows(attempt / 'ego_turn_motion.jsonl')
    signal = rows(attempt / 'ego_signal_audio.jsonl')
    bodies = rows(attempt / 'participant_bodies.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    pcm = rows(attempt / 'listener_audio_original.jsonl')
    require(len(motion) >= 2 and all(len(part) == len(motion) for part in
            (signal, bodies, frames, trace, pcm)), 'Incomplete original turn frame inventory')
    for index, (move, sig, body, frame, point, packet) in enumerate(
            zip(motion, signal, bodies, frames, trace, pcm)):
        identity = (move['frame'], move['time_s'])
        require((sig['frame'], sig['time_s']) == identity
                and (body['frame'], body['time_s']) == identity
                and (frame['carla_frame'], frame['time_s']) == identity
                and (point['frame'], point['time_s']) == identity
                and frame['video_frame'] == index and packet['frame'] == identity[0],
                'Original turn frame join differs')
        require(packet['sha256'] == sig['listener_packet_sha256']
                and packet['samples'] == sig['listener_audio_samples'],
                'Original listener PCM packet differs')
        if case.endswith('__other_vehicle_signal_before_turn'):
            require(packet['origin'] == 'not_collected_no_affected_pedestrian'
                    and sig['listener_audio_status'] == packet['origin'],
                    'No-pedestrian listener status differs')
        else:
            require(packet['origin'] == 'listener_pcm_capture'
                    and sig['listener_audio_status'] == 'original_pcm',
                    'Original listener PCM provenance differs')
    value = observed['value']
    require(value['frame_count'] == len(motion)
            and value['turn_onset_frame'] in {row['frame'] for row in motion}
            and value['clearly_audible_legal_judgment'] is None
            and value['reasonable_safety_legal_judgment'] is None
            and not report.get('physical_acceptance_claimed')
            and not report.get('legal_acceptance_claimed'),
            'Turn observation or unresolved legal finding differs')
    if 'horn_actuation.jsonl' in hashes:
        acts = rows(attempt / 'horn_actuation.jsonl')
        require(bool(acts) and all(
                row['request']['nonce'] == row['acknowledgement']['nonce']
                and row['request']['frame'] == row['acknowledgement']['frame']
                and row['request']['frame'] < value['turn_onset_frame']
                and row['physical_sound_verified'] is False for row in acts),
                'Original horn relay timing differs')
    for name in VIDEOS:
        audit_video(attempt / name, len(frames), mapping_sha256=hashes['video_frames.jsonl'])
    return {'format': 'worker-turn-delivery-source-audit', 'case_id': case,
            'joined_frames': len(frames), 'decoded_cameras': list(VIDEOS),
            'source_integrity_passed': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processed', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.processed, args.negative), indent=2))
