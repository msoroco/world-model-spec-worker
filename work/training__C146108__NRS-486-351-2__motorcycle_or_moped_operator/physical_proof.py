"""Source-shaped motorcycle motion and lifecycle CPU diagnostic; no Native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from native.measure_follow import measure as measure_follow
from native.measure_pass import measure as measure_pass

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
    follow = config['case_id'].endswith('__controlled_1')
    poses = [json.loads(line) for line in
             (attempt / 'participant-poses.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in
              (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(poses) != len(frames) or len(poses) != 600 or any(
            row['native_frame'] != frame['native_frame'] or
            row['video_frame'] != frame['video_frame']
            for row, frame in zip(poses, frames)):
        raise ValueError('Synthetic motorcycle source frame join incomplete')
    sources = {name: sha(attempt / name) for name in
               ('participant-poses.jsonl', 'video_frames.jsonl',
                'pass-context.json', 'road.xodr')}
    if kind == 'missing_evidence':
        status, observed = 'unverified', {}
        mutation = 'Rider body source omitted from assessor input'
    else:
        measured = measure_follow(attempt) if follow else measure_pass(attempt)
        if follow:
            original_met = (measured['same_lane_all_frames'] and
                            measured['longitudinal_overlap_frames'] == 0)
            incomplete_met = False  # Rider acceleration would create body overlap.
        else:
            original_met = (measured['first_behind_frame'] <
                            measured['first_overlap_frame'] <
                            measured['first_clear_ahead_frame'])
            incomplete_met = False  # Matched speeds would leave rider behind.
        status = ('met' if original_met else 'not_met') if kind == 'complete_motion' else (
            'met' if incomplete_met else 'not_met')
        mutation = ('Unmodified source-shaped 600-frame motorcycle history' if
                    kind == 'complete_motion' else
                    'Counterfactual rider speed removes the selected following/pass distinction')
        observed = {'same_lane_episode': measured,
                    'target_distinction': 'following' if follow else 'behind_to_ahead_pass',
                    'original_native_motion_verified': False}
    return {'case_id': config['case_id'], 'fixture_kind': kind,
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False, 'synthetic_mutation': mutation,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'Source-joined synthetic full-body motorcycle positions and original frame map with incomplete/missing counterfactuals',
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
        Path(args.output).write_text(json.dumps(result, indent=2).rstrip() + '\n')
        print(args.kind, result['physical_checks']['maneuver']['status'])
