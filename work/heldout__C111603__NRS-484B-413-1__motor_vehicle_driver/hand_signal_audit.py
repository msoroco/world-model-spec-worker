"""Independently bind the hand alternative to original frames and four videos."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video
from turn_hand_signal import measure as measure_hand
from turn_signal_measurement import measure as measure_turn

CASE = ROOT.name + '__vehicle_hand_signal'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt, *, corrupt=False):
    root = Path(attempt)
    report = json.loads((root / 'analysis-report.json').read_text())
    if report.get('case_id') != CASE or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Wrong or overclaimed hand-signal report')
    originals = (*SOURCES, 'hand_signal_original.jsonl', 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)
    hashes = {name: sha(root / name) for name in originals}
    turn = report['measurements']['turn_signal_observation']
    hand = report['measurements']['hand_signal_observation']
    if corrupt:
        hashes['hand_signal_original.jsonl'] = '0' * 64
    if turn.get('sources') != hashes:
        raise ValueError('Stale or missing original hand-signal source')
    if hand.get('sources') != {name: hashes[name] for name in ('hand_signal_original.jsonl', 'ego_turn_motion.jsonl')}:
        raise ValueError('Stale or missing original hand measurement source')
    measured_turn = measure_turn(*(root / name for name in SOURCES))
    measured_hand = measure_hand(root / 'hand_signal_original.jsonl', root / 'ego_turn_motion.jsonl')
    if turn['value'] != measured_turn or hand['value'] != measured_hand:
        raise ValueError('Hand-signal measurement differs from originals')
    if measured_turn['pre_turn_indicator_frames'] or not measured_turn['vehicle_may_be_affected']:
        raise ValueError('Hand alternative signal or participant context differs')
    mapping, trace = rows(root / 'video_frames.jsonl'), rows(root / 'trace.jsonl')
    if len(mapping) != len(trace) or len(mapping) != measured_hand['frame_count']:
        raise ValueError('Hand/video/trace frame inventory differs')
    for index, (mapped, point) in enumerate(zip(mapping, trace)):
        if (mapped.get('video_frame') != index or
            (mapped.get('carla_frame'), mapped.get('time_s')) !=
            (point.get('frame'), point.get('time_s'))):
            raise ValueError('Hand/video/trace frame join differs')
    for name in VIDEOS:
        audit_video(root / name, len(mapping), mapping_sha256=hashes['video_frames.jsonl'])
    return {'format': 'worker-hand-signal-source-audit', 'case_id': CASE,
            'original_source_sha256': hashes, 'joined_frames': len(mapping),
            'video_decode_count': 4, 'physical_visibility_verified': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--corrupt', action='store_true')
    args = parser.parse_args()
    receipt = audit(args.attempt, corrupt=args.corrupt)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'joined_frames': receipt['joined_frames'], 'video_decode_count': 4}))


if __name__ == '__main__':
    main()
