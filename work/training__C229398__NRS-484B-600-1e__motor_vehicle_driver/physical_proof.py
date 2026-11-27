"""Synthetic curb-completion and lifecycle probes; no Native acceptance claim."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_measure import measure, rows

ORDER = ('capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lifecycle(events):
    if tuple(events) != ORDER:
        raise ValueError('Saved processing precedes Native ownership closure')
    return True


def evaluate(attempt, kind):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case_id']
    path = attempt / 'native-speed.jsonl'
    fmap = attempt / 'video_frames.jsonl'
    sources = {'native-speed.jsonl': sha(path),
               'video_frames.jsonl': sha(fmap),
               'road.xodr': sha(attempt / 'road.xodr')}
    samples, frames = rows(path), rows(fmap)
    if len(samples) != len(frames) or len(samples) != 600 or any(
            sample['native_frame'] != frame['native_frame'] or
            sample['frame'] != frame['video_frame']
            for sample, frame in zip(samples, frames)):
        raise ValueError('Synthetic source frame join incomplete')
    if kind == 'missing_evidence':
        samples = []
        mutation = 'Native speed source unavailable to the diagnostic assessor'
    elif kind == 'incomplete_motion':
        samples = [dict(row, sample=dict(row['sample'])) for row in samples]
        for row in samples[520:]:
            row['sample']['lane_id'] = -1
        mutation = 'Parked interval remains in driving lane -1'
    else:
        mutation = 'Unmodified synthetic diagnostic source'
    if not samples:
        status = 'unverified'
        observed = {}
    else:
        original = measure(attempt, case, diagnostic=True)
        driving = all(row['phase'] == 'approach_driving' and
                      row['sample']['lane_id'] == -1 for row in samples[:400])
        parked = all(row['phase'] == 'parked' and
                     row['sample']['lane_id'] == -2 and
                     row['sample']['observed_speed_mph'] <= .5
                     for row in samples[520:])
        status = 'met' if driving and parked else 'not_met'
        observed = {'approach_frames': len(samples[:400]),
                    'parked_frames': len(samples[520:]),
                    'max_approach_speed_mph': original['max_approach_speed_mph'],
                    'parked_curb_lane_observed': parked,
                    'original_native_observed': False}
        sources.update(original['source_sha256'])
    return {'case_id': case, 'fixture_kind': kind,
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'synthetic_mutation': mutation,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'Synthetic source-joined approach-driving and parked curb lane/readback, with controlled incomplete/missing mutations',
                'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': observed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt')
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence'))
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + (ORDER[-1], ORDER[-2]))
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError('Premature saved processing accepted')
        print('Capture ownership closure precedes saved processing')
    else:
        result = evaluate(args.attempt, args.kind)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(args.kind, result['physical_checks']['maneuver']['status'])
