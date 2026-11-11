"""Independently compare original participant geometry and full video for a narrower turn."""
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

CASE = ROOT.name + '__clearance_narrow'
BASE = ROOT.name + '__vehicle_left_indicator'
SOURCES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
           'affected_participants.json', 'participant_bodies.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt, baseline, *, negative=False):
    root, other = Path(attempt), Path(baseline)
    report = json.loads((root / 'analysis-report.json').read_text())
    if report.get('case_id') != CASE or report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Wrong or overclaimed narrow-clearance report')
    measured = report['measurements']['turn_signal_observation']
    hashes = {name: sha(root / name) for name in (*SOURCES, 'video_frames.jsonl', 'trace.jsonl', *VIDEOS)}
    if negative:
        measured['sources']['participant_bodies.jsonl'] = '0' * 64
    if measured.get('sources') != hashes:
        raise ValueError('Stale or missing original clearance source')
    narrow = measure(*(root / name for name in SOURCES))
    baseline = measure(*(other / name for name in SOURCES))
    if narrow != measured['value']:
        raise ValueError('Clearance report differs from original-source recomputation')
    if narrow['reasonable_safety_legal_judgment'] is not None or baseline['reasonable_safety_legal_judgment'] is not None:
        raise ValueError('Reasonable safety was prematurely decided')
    for name in ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                 'affected_participants.json', 'trace.jsonl', 'video_frames.jsonl', *VIDEOS):
        if sha(root / name) != sha(other / name):
            raise ValueError('Clearance pair changed non-geometry source: ' + name)
    first, second = rows(other / 'participant_bodies.jsonl'), rows(root / 'participant_bodies.jsonl')
    if len(first) != len(second) or len(first) != narrow['frame_count']:
        raise ValueError('Clearance pair frame counts differ')
    for a, b in zip(first, second):
        if b['bodies']['affected_vehicle']['x_m'] != a['bodies']['affected_vehicle']['x_m'] or \
           b['bodies']['affected_vehicle']['y_m'] != a['bodies']['affected_vehicle']['y_m'] - 1:
            raise ValueError('Affected vehicle offset differs')
        a = json.loads(json.dumps(a)); b = json.loads(json.dumps(b))
        a['bodies']['affected_vehicle']['x_m'] = b['bodies']['affected_vehicle']['x_m']
        a['bodies']['affected_vehicle']['y_m'] = b['bodies']['affected_vehicle']['y_m']
        if a != b:
            raise ValueError('Clearance pair changed another participant field')
    narrow_gap = narrow['participant_clearance']['affected_vehicle']
    baseline_gap = baseline['participant_clearance']['affected_vehicle']
    if narrow_gap['minimum_sampled_surface_gap_m'] >= baseline_gap['minimum_sampled_surface_gap_m'] or \
       narrow_gap['surface_gap_at_turn_onset_m'] >= baseline_gap['surface_gap_at_turn_onset_m']:
        raise ValueError('Original sampled gap did not narrow')
    mapping, trace = rows(root / 'video_frames.jsonl'), rows(root / 'trace.jsonl')
    if len(mapping) != len(trace) or len(mapping) != narrow['frame_count']:
        raise ValueError('Original video/trace frame count differs')
    for index, (mapped, point) in enumerate(zip(mapping, trace)):
        if mapped.get('video_frame') != index or \
           (mapped.get('carla_frame'), mapped.get('time_s')) != (point.get('frame'), point.get('time_s')):
            raise ValueError('Original video/trace join differs')
    for name in VIDEOS:
        audit_video(root / name, len(mapping), mapping_sha256=hashes['video_frames.jsonl'])
    return {'format': 'worker-clearance-pair-audit', 'case_id': CASE, 'baseline_case_id': BASE,
            'source_integrity_passed': True, 'controlled_pair_passed': True,
            'video_decode_count': 4, 'joined_frames': len(mapping),
            'baseline_minimum_sampled_gap_m': baseline_gap['minimum_sampled_surface_gap_m'],
            'narrow_minimum_sampled_gap_m': narrow_gap['minimum_sampled_surface_gap_m'],
            'baseline_gap_at_turn_onset_m': baseline_gap['surface_gap_at_turn_onset_m'],
            'narrow_gap_at_turn_onset_m': narrow_gap['surface_gap_at_turn_onset_m'],
            'physical_safety_verified': False, 'legal_acceptance_claimed': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--attempt', required=True)
    p.add_argument('--baseline', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--negative', action='store_true')
    args = p.parse_args()
    if args.case != CASE:
        raise ValueError('Wrong exact clearance audit case')
    receipt = audit(args.attempt, args.baseline, negative=args.negative)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'controlled_pair_passed': True,
                      'baseline_gap_m': receipt['baseline_minimum_sampled_gap_m'],
                      'narrow_gap_m': receipt['narrow_minimum_sampled_gap_m']}))


if __name__ == '__main__':
    main()
