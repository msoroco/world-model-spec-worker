"""Source-shaped travel completion and capture lifecycle CPU checks."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(trace, mapping, direction, minimum):
    if len(trace) != 600 or len(mapping) != 600:
        return 'unverified', {}, 'Missing complete 600-frame original motion or frame map'
    for i, (motion, frame) in enumerate(zip(trace, mapping)):
        if (motion.get('frame') != frame.get('native_frame') or
                frame.get('video_frame') != i or
                abs(motion.get('time_s', -1) - frame.get('time_s', -2)) > 1e-8):
            return 'unverified', {}, 'Original motion and frame identity differ'
    sign = 1 if direction == 'designated' else -1
    progress = sign * (trace[-1]['position_m'][0] - trace[0]['position_m'][0])
    status = 'met' if progress >= minimum else 'not_met'
    realized = {'measured_projected_progress_m': round(progress, 3),
                'engineering_minimum_progress_m': minimum,
                'requested_direction': direction,
                'sample_count': 600}
    return status, realized, 'Original-frame projected travel progress on the authored governed road'


def physical(direction, kind):
    if direction not in ('designated', 'opposite') or kind not in (
            'complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact case or physical fixture')
    path = HERE / 'cases' / direction / 'fixture-spec.json'
    spec = json.loads(path.read_text())
    trace = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines()]
    mapping = [json.loads(line) for line in spec['files']['video_frames.jsonl'].splitlines()]
    if kind == 'incomplete_motion':
        for row in trace:
            row['position_m'][0] = trace[0]['position_m'][0]
            row['velocity_mps'][0] = 0
    if kind == 'missing_evidence':
        trace.pop(300)
    status, realized, method = assess(trace, mapping, direction, 120)
    if status != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                  'missing_evidence': 'unverified'}[kind]:
        raise ValueError('Physical fixture yielded wrong source-based outcome')
    return {'format': 'nrs-484b-220-1-physical-fixture-v1',
            'case_id': HERE.name + '__' + direction, 'kind': kind,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status, 'method': method,
                                             'sources': {'fixture-spec.json': sha(path),
                                                         'road.xodr': sha(HERE / 'selected' / 'road.xodr')}}},
            'maneuver_completed': status == 'met',
            'realized_observables': realized, 'physical_or_legal_acceptance': False}


def lifecycle():
    def checked(events):
        if events != EVENTS:
            raise ValueError('Saved processing preceded Native owner release or restoration')
    checked(EVENTS)
    try:
        checked(EVENTS[:4] + EVENTS[5:] + EVENTS[4:5])
    except ValueError:
        pass
    else:
        raise ValueError('Out-of-order lifecycle accepted')
    return {'format': 'nrs-484b-220-1-lifecycle-fixture-v1', 'events': EVENTS,
            'recorded_only': True, 'originals_preserved': True,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = lifecycle() if args.kind == 'lifecycle' else physical(args.case, args.kind)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'case': args.case, 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))
