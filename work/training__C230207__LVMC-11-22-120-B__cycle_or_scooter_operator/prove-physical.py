"""Exercise source-joined bicycle motion completion without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(suffix, kind):
    source = HERE / 'cases' / suffix / 'diagnostic.json'
    files = json.loads(source.read_text())['files']
    poses = [json.loads(line) for line in files['bicycle-poses.jsonl'].splitlines()]
    mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
    if len(poses) != 600 or len(mapping) != 600:
        raise ValueError('Expected 600 original-shaped source and frame rows')
    ref = {'path': str(source.relative_to(HERE)), 'sha256': sha(source),
           'embedded_sources': ['files.bicycle-poses.jsonl', 'files.video_frames.jsonl']}
    if kind == 'missing_evidence':
        return {'status': 'unverified', 'method': 'original pose and four-camera FrameMap join',
                'sources': [ref], 'reason': 'pose source deliberately withheld'}
    selected = poses if kind == 'complete_motion' else poses[:20]
    for pose, frame in zip(selected, mapping):
        if (pose['native_frame'] != frame['carla_frame'] or
                abs(pose['time_s'] - frame['time_s']) > 1e-6 or
                pose['rider_actor_id'] != 1 or
                pose['rider_blueprint_id'] != 'vehicle.bh.crossbike'):
            raise ValueError('Source identity/frame join differs')
    progress = selected[-1]['rider_xy_m'][0] - selected[0]['rider_xy_m'][0]
    met = len(selected) == 600 and progress >= 10
    if met != (kind == 'complete_motion'):
        raise ValueError('Requested physical fixture outcome differs')
    return {'status': 'met' if met else 'not_met',
            'method': 'source-joined 600-frame bicycle displacement; 10 m engineering completion milestone',
            'sources': [ref], 'sample_count': len(selected), 'forward_progress_m': progress,
            'legal_threshold_claimed': False, 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('probe_01', 'probe_02'), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        if events.index('owner_released') >= events.index('saved_processing_started'):
            raise ValueError('Premature saved processing')
        print(json.dumps({'events': events, 'premature_processing_rejected': True,
                          'fixture_only': True}, sort_keys=True))
        return
    if not args.output:
        parser.error('--output required')
    check = assess(args.case, args.kind)
    result = {'format': 'c230207-signed-bicycle-synthetic-physical-v1',
              'case_id': HERE.name + '__' + args.case,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'native_executed': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False, 'physical_checks': {'maneuver': check},
              'maneuver_completed': check['status'] == 'met',
              'realized_observables': {'rider_forward_progress_m': {
                  'value': check['forward_progress_m'], 'unit': 'm',
                  'method': check['method'], 'sources': check['sources']}}
              if check['status'] == 'met' else {}}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'status': check['status'],
                      'result_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    main()
