"""Exercise selected physical completion classification on retained synthetic rows."""
import argparse
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CASES = ('probe_1', 'probe_2', 'yield_wait_for_clearance',
         'yield_enter_during_occupancy')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(case, kind):
    if case not in CASES:
        raise ValueError('Unknown selected case')
    source = BASE / 'selected-native' / case / 'physical-source.jsonl'
    construction = BASE / 'selected-native' / case / 'construction.json'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Full synthetic source requires 600 joined frames')
    common = {'case_id': BASE.name + '__' + case,
              'construction_sha256': sha(construction),
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'original_native_motion_verified': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        return dict(common, events=EVENTS, exit_code=0)
    if kind == 'incomplete_motion':
        rows = rows[:150]
    elif kind == 'missing_evidence':
        rows = []
    elif kind != 'complete_motion':
        raise ValueError('Unknown fixture kind')
    joined = bool(rows) and all(row['native_frame'] == row['video_native_frame']
                                and abs(row['native_time_s'] - row['video_time_s']) < 1e-6
                                for row in rows)
    entry = any(row['entered_intersection'] for row in rows)
    progress = (rows[-1]['body_center_y_m'] - rows[0]['body_center_y_m']) if rows else 0.0
    complete = len(rows) == 600 and joined and entry and progress >= 4.0
    status = 'unverified' if not rows else 'met' if complete else 'not_met'
    return dict(common, physical_checks={'maneuver': {
        'status': status,
        'method': 'synthetic full-body center displacement, intersection entry and 600-frame time join',
        'sources': [str(source.relative_to(BASE))],
        'details': {'sample_count': len(rows), 'progress_m': progress,
                    'entered_intersection': entry, 'joined': joined,
                    'engineering_fixture_only': True}}},
        maneuver_completed=complete,
        realized_observables=({'sample_count': len(rows), 'progress_m': progress,
                               'entered_intersection': entry, 'joined': joined} if rows else {}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = evaluate(args.case, args.kind)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle'),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
