"""Independent original-source and controlled-pair audit for no-indicator turn."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video
from turn_signal_measurement import measure

CASE = ROOT.name + '__vehicle_no_indicator'
POSITIVE = ROOT.name + '__vehicle_left_indicator'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt, positive, *, negative=False):
    root, other = Path(attempt), Path(positive)
    report = json.loads((root / 'analysis-report.json').read_text())
    if report.get('case_id') != CASE or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Wrong or overclaimed no-indicator delivery report')
    measured = report['measurements']['turn_signal_observation']
    hashes = {name: sha(root / name) for name in (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    if negative:
        measured['sources']['ego_signal_audio.jsonl'] = '0' * 64
    if measured.get('sources') != hashes:
        raise ValueError('Stale or missing original no-indicator source')
    absent = measure(*(root / name for name in SOURCES))
    present = measure(*(other / name for name in SOURCES))
    if absent != measured['value'] or absent['pre_turn_indicator_frames'] or not present['pre_turn_indicator_frames']:
        raise ValueError('Original signal contrast differs')
    if absent['pedestrian_may_be_affected'] or not absent['vehicle_may_be_affected']:
        raise ValueError('Affected participant context differs')
    for name in ('ego_turn_motion.jsonl', 'affected_participants.json',
                 'participant_bodies.jsonl', 'trace.jsonl', 'video_frames.jsonl', *VIDEOS):
        if sha(root / name) != sha(other / name):
            raise ValueError('Controlled pair changed non-signal source: ' + name)
    first, second = rows(other / 'ego_signal_audio.jsonl'), rows(root / 'ego_signal_audio.jsonl')
    if len(first) != len(second):
        raise ValueError('Controlled pair signal frames differ')
    for a, b in zip(first, second):
        if b.get('indicator_readback') != 'off' or a.get('indicator_readback') not in ('off', 'left'):
            raise ValueError('Controlled pair indicator states differ')
        a = dict(a); b = dict(b)
        a.pop('indicator_readback'); b.pop('indicator_readback')
        if a != b:
            raise ValueError('Controlled pair changed another signal/audio field')
    mapping = rows(root / 'video_frames.jsonl')
    trace = rows(root / 'trace.jsonl')
    if len(mapping) != len(trace) or len(mapping) != absent['frame_count']:
        raise ValueError('No-indicator video/trace frame count differs')
    for index, (mapped, point) in enumerate(zip(mapping, trace)):
        if (mapped.get('video_frame') != index or
            (mapped.get('carla_frame'), mapped.get('time_s')) !=
            (point.get('frame'), point.get('time_s'))):
            raise ValueError('No-indicator video/trace join differs')
    for name in VIDEOS:
        audit_video(root / name, len(mapping), mapping_sha256=hashes['video_frames.jsonl'])
    return {'format': 'worker-no-indicator-pair-audit', 'case_id': CASE,
            'positive_case_id': POSITIVE, 'source_integrity_passed': True,
            'controlled_pair_passed': True, 'video_decode_count': 4,
            'joined_frames': len(mapping),
            'positive_pre_turn_indicator_frames': present['pre_turn_indicator_frames'],
            'absent_pre_turn_indicator_frames': absent['pre_turn_indicator_frames'],
            'physical_visibility_verified': False, 'legal_acceptance_claimed': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--attempt', required=True)
    p.add_argument('--positive', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--negative', action='store_true')
    args = p.parse_args()
    if args.case != CASE:
        raise ValueError('Wrong exact no-indicator audit case')
    receipt = audit(args.attempt, args.positive, negative=args.negative)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'controlled_pair_passed': True, 'joined_frames': receipt['joined_frames']}))


if __name__ == '__main__':
    main()
