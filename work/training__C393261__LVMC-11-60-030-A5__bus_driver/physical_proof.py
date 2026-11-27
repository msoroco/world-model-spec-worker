"""Synthetic bus-stop motion and lifecycle diagnostics; no Native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure

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
    history = [json.loads(line) for line in
               (attempt / 'terminus-history.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in
              (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(history) != len(frames) or len(history) != 600 or any(
            row['native_frame'] != frame['native_frame'] or
            row['video_frame'] != frame['video_frame']
            for row, frame in zip(history, frames)):
        raise ValueError('Synthetic bus source frame join incomplete')
    sources = {name: sha(attempt / name) for name in
               ('terminus-history.jsonl', 'video_frames.jsonl',
                'terminus-context.json', 'road.xodr')}
    if kind == 'missing_evidence':
        status, observed = 'unverified', {}
        mutation = 'Bus history omitted from assessor input'
    else:
        actual = measure(attempt / 'terminus-history.jsonl',
                         attempt / 'terminus-context.json')
        target = config['physical_target']['target_dwell_s']
        stationary = actual['longest_complete_interval_s']
        if kind == 'incomplete_motion':
            mutated = [dict(row) for row in history]
            for row in mutated:
                if row.get('controller_state') == 'parked':
                    row['velocity_xyz_mps'] = [2.0, 0.0, 0.0]
            dwell_rows = [row for row in mutated if row.get('controller_state') == 'parked' and
                          sum(v * v for v in row['velocity_xyz_mps']) ** .5 < .25]
            status = 'met' if len(dwell_rows) / 20 >= target else 'not_met'
            mutation = 'Source parked rows mutated to moving velocity of 2 m/s'
        else:
            status = 'met' if abs(stationary - target) <= .25 else 'not_met'
            mutation = 'Unmodified source-shaped synthetic bus history'
        observed = {'measured_complete_stationary_dwell_s': stationary,
                    'target_dwell_s': target,
                    'stationary_motion_verified_in_original_native': False}
    return {'case_id': config['case_id'], 'fixture_kind': kind,
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False, 'synthetic_mutation': mutation,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'Source-joined synthetic bus pose/velocity and endpoint interval with incomplete/missing mutations',
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
        print('Native ownership closure precedes saved processing')
    else:
        result = evaluate(args.attempt, args.kind)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(args.kind, result['physical_checks']['maneuver']['status'])
