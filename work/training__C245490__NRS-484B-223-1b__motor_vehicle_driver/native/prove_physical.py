"""Classify three synthetic motion states and the saved-processing event order."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_lane_change import measure, read_trace

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
CASES = ('signal_before_safe', 'signal_after_safe',
         'signal_before_unsafe', 'signal_before_no_check')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(case, kind):
    if not case.startswith(PACKAGE.name + '__'):
        raise ValueError('Wrong exact assignment')
    suffix = case[len(PACKAGE.name) + 2:]
    if suffix not in CASES:
        raise ValueError('Unknown selected case')
    source = PACKAGE / 'selected-source' / suffix
    motion_path = source / 'native-ego-frames.jsonl'
    check_path = source / 'native-driver-checks.jsonl'
    original = read_trace(motion_path)
    checks = read_trace(check_path)
    if len(original) != 600 or len(checks) != 1:
        raise ValueError('Synthetic diagnostic source incomplete')
    base = {'case_id': case,
            'construction_sha256': sha(HERE / 'selected' / suffix / 'construction.json'),
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_motion_verified': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        if not (EVENTS.index('native_exit') < EVENTS.index('owner_released') <
                EVENTS.index('saved_processing_started')):
            raise ValueError('Saved processing began before Native owner release')
        return dict(base, events=EVENTS, exit_code=0)
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown synthetic physical fixture')
    if kind == 'missing_evidence':
        rows = original
        available_checks = []
    elif kind == 'incomplete_motion':
        rows = original[:150]
        available_checks = checks
    else:
        rows = original
        available_checks = checks
    joined = all(row['video_frame'] == i and row['time_s'] == i / 20
                 for i, row in enumerate(rows))
    if not joined:
        raise ValueError('Synthetic motion source frame join changed')
    departure = next((i for i, row in enumerate(rows)
                      if abs(row['ego_lateral_offset_from_occupied_lane_center_m']) +
                      row['ego_body_half_width_m'] > row['occupied_lane_half_width_m']), None)
    if kind == 'complete_motion':
        observed = measure(rows, 'synthetic_native_sample', available_checks)
        complete = observed['activation_observed'] and departure is not None
        status = 'met' if complete else 'not_met'
        if status != 'met':
            raise ValueError('Complete fixture did not actually depart occupied lane')
    elif kind == 'incomplete_motion':
        complete = False
        status = 'not_met'
        if departure is not None:
            raise ValueError('Incomplete fixture already departed occupied lane')
    else:
        complete = False
        status = 'unverified'
    return dict(base,
                physical_checks={'maneuver': {
                    'status': status,
                    'method': 'source-frame joined original-body boundary departure in labelled synthetic Native diagnostic',
                    'sources': [str(motion_path.relative_to(PACKAGE)),
                                str(check_path.relative_to(PACKAGE))],
                    'details': {'sample_count': len(rows), 'source_joined': joined,
                                'departure_frame': departure,
                                'independent_check_source_present': bool(available_checks),
                                'engineering_fixture_only': True}}},
                maneuver_completed=bool(complete),
                realized_observables=({'sample_count': len(rows),
                                       'departure_frame': departure} if complete else {}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = classify(args.case, args.kind)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'physical_status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
