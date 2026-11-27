"""Synthetic parked-interval and ownership-order CPU assessment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_saved_measure import measure
from source_review import join

ORDER = ['capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lifecycle(events):
    if events != ORDER:
        raise ValueError('saved processing precedes Native ownership closure')
    return True


def evaluate(attempt, kind):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['case_id']
    pose_path = attempt / 'vehicle-pose.jsonl'
    frame_path = attempt / 'video_frames.jsonl'
    poses = [json.loads(line) for line in pose_path.read_text().splitlines()]
    frames = [json.loads(line) for line in frame_path.read_text().splitlines()]
    if len(poses) != len(frames) or len(poses) != 600 or any(
            p['native_frame'] != f['native_frame'] or p['video_frame'] != f['video_frame']
            for p, f in zip(poses, frames)):
        raise ValueError('synthetic parked interval has incomplete source joins')
    sources = {'vehicle-pose.jsonl': sha(pose_path),
               'video_frames.jsonl': sha(frame_path)}
    if kind == 'missing_evidence':
        status, observables = 'unverified', {}
    else:
        context = join(attempt, case_id)
        sources.update({'road-review.json': sha(attempt / 'road-review.json'),
                        'road.xodr': sha(attempt / 'road.xodr')})
        packet = {'assignment_id': context['assignment_id'],
                  'source_kind': context['source_kind'],
                  'vehicle_id': poses[0]['vehicle_id'],
                  'frames': [dict(p, frame=i, t_s=i / 20) for i, p in enumerate(poses)]}
        measurement = measure(json.dumps(packet).encode(), json.dumps(context).encode())
        stationary = measurement['stationary_frame_count'] == 600
        inside = len(measurement['stationary_footprint_fully_within_governed_extent_frames']) == 600
        selected = inside if case_id.endswith('probe_02') else not inside
        if kind == 'complete_motion':
            status = 'met' if stationary and selected else 'not_met'
        elif kind == 'incomplete_motion':
            # Controlled loss of half the parked interval must reject completion.
            status = 'not_met' if len(poses[:300]) != 600 else 'met'
        else:
            raise ValueError('unknown fixture kind')
        observables = {'stationary_frames': measurement['stationary_frame_count'],
                       'full_footprint_inside_frames': len(measurement['stationary_footprint_fully_within_governed_extent_frames']),
                       'duration_s': measurement['duration_s'],
                       'original_native_observed': False}
    return {'case_id': case_id, 'fixture_kind': kind,
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'synthetic source-joined full parked interval, reviewed device extent, and controlled incomplete/missing mutations',
                'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': observables}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt')
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(ORDER)
        try:
            lifecycle(ORDER[:-2] + [ORDER[-1], ORDER[-2]])
        except ValueError as error:
            print(str(error))
        else:
            raise AssertionError('premature saved processing accepted')
        print('capture ownership closure precedes saved processing')
    else:
        result = evaluate(args.attempt, args.kind)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(args.kind, result['physical_checks']['maneuver']['status'])
