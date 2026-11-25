"""CPU diagnostic of source-shaped turn progress and capture ownership order."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHORTS = ('controlled_1', 'controlled_2', 'pedestrian_clearance',
          'pedestrian_overlap', 'concurrent_absent', 'concurrent_present')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def prove(short, kind):
    if short not in SHORTS:
        raise ValueError('Unknown selected case')
    construction = json.loads((ROOT / f'native/selected-{short}-primary-construction.json').read_text())
    from hashlib import sha256
    source = ROOT / f'selected-source-{short}'
    trace_path = source / 'trace.jsonl'
    join_path = source / 'video_frames.jsonl'
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    video = [json.loads(line) for line in join_path.read_text().splitlines()]
    if len(trace) != 600 or len(video) != 600:
        raise ValueError('The positive diagnostic source needs 600 frames')
    base = {
        'case_id': construction['case_id'],
        'construction_sha256': sha256((ROOT / f'native/selected-{short}-primary-construction.json').read_bytes()).hexdigest(),
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'original_native_motion_verified': False,
        'legal_verdict_claimed': False,
        'cautiousness_legal_judgment': None,
    }
    if kind == 'lifecycle':
        return dict(base, events=EVENTS, exit_code=0)
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown fixture kind')
    if kind == 'incomplete_motion':
        trace = trace[:150]
    elif kind == 'missing_evidence':
        trace = []
    joined = bool(trace) and all(
        row['frame'] == frame.get('frame', frame.get('native_frame'))
        and abs(row['time_s'] - frame['time_s']) < 1e-6
        for row, frame in zip(trace, video)
    )
    progress = math.dist(trace[0]['position_m'][:2], trace[-1]['position_m'][:2]) if trace else 0.0
    complete = len(trace) == 600 and joined and progress >= 8.0
    status = 'unverified' if not trace else 'met' if complete else 'not_met'
    return dict(base, physical_checks={'maneuver': {
        'status': status,
        'method': 'source-shaped frame/time join and 8 m engineering route progress',
        'sources': [f'selected-source-{short}/trace.jsonl',
                    f'selected-source-{short}/video_frames.jsonl'],
        'details': {'sample_count': len(trace), 'progress_m': progress,
                    'joined': joined, 'not_a_legal_threshold': True},
    }}, maneuver_completed=complete,
        realized_observables=({'sample_count': len(trace), 'progress_m': progress,
                               'joined': joined} if trace else {}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prove(args.case, args.kind)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle'),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
