"""CPU fixture for original-travel completion and saved-only lifecycle checks.

All fixture outputs declare synthetic provenance. The local independent audit
must revisit these predicates on original Native sources before acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LIFECYCLE = ['capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started']


def require(value, message):
    if not value:
        raise ValueError(message)


def measure(rows, case_id, source_sha):
    require(len(rows) == 600, '600 source frames required')
    before = None
    moving = governed = matching = 0
    expected_on = case_id.endswith('__controlled_1')
    for index, row in enumerate(rows):
        require(row.get('video_frame') == index and row.get('native_frame') is not None,
                'original frame identity missing')
        native = row['native_frame']
        require(type(native) is int and (before is None or native > before),
                'Native frame order changed')
        before = native
        require(abs(row.get('time_s', -1) - index / 20) < 1e-8,
                'source time changed')
        speed = row.get('speed_mps')
        require(type(speed) in (int, float) and speed >= 0,
                'speed source missing')
        moving += speed > .1
        active = row.get('device_active')
        require(type(active) is bool, 'device timing source missing')
        governed += active
        if active:
            matching += (row.get('headlamp_setting_on') is expected_on and
                         row.get('position_lamp_setting_on') is expected_on)
    status = 'met' if moving >= 400 and governed >= 200 else 'not_met'
    return {
        'case_id': case_id,
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'source-joined 600-frame travel and governed-road counts',
            'sources': [{'path': 'vehicle-lamps.jsonl', 'sha256': source_sha}],
            'moving_frames': moving, 'governed_frames': governed,
            'requested_setting_matching_frames': matching,
            'legal_verdict_claimed': False}},
        'maneuver_completed': status == 'met',
        'realized_observables': ({'moving_frames': {'value': moving, 'unit': 'frames',
                                                   'method': 'original speed readback fixture'}}
                                 if status == 'met' else {}),
        'accepted': False,
        'legal_verdict_claimed': False,
    }


def lifecycle(events):
    require(events == LIFECYCLE, 'saved processing precedes owner release')
    return {'events': events, 'exit_code': 0, 'original_capture_claimed': False}


def fixture(case_id, kind, source):
    raw = Path(source).read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if kind == 'incomplete_motion':
        for row in rows:
            row['speed_mps'] = 0
    elif kind == 'missing_evidence':
        rows[200].pop('speed_mps', None)
    try:
        result = measure(rows, case_id, hashlib.sha256(raw).hexdigest())
    except ValueError as error:
        require(kind == 'missing_evidence' and 'speed source missing' in str(error),
                'unexpected fixture rejection')
        result = {'case_id': case_id, 'provenance_kind': 'synthetic_fixture',
                  'diagnostic_fixture': True,
                  'physical_checks': {'maneuver': {
                      'status': 'unverified', 'method': 'missing source rejection',
                      'sources': [{'path': 'vehicle-lamps.jsonl',
                                   'sha256': hashlib.sha256(raw).hexdigest()}],
                      'error': str(error)}},
                  'maneuver_completed': False, 'realized_observables': {},
                  'accepted': False, 'legal_verdict_claimed': False}
    if kind == 'complete_motion':
        require(result['physical_checks']['maneuver']['status'] == 'met',
                'complete fixture lacks travel')
    if kind == 'incomplete_motion':
        require(result['physical_checks']['maneuver']['status'] == 'not_met',
                'incomplete fixture passed')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--source')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        result = lifecycle(LIFECYCLE)
        try:
            lifecycle(LIFECYCLE[:-2] + LIFECYCLE[-2:][::-1])
        except ValueError:
            pass
        else:
            raise AssertionError('premature saved processing accepted')
    else:
        require(args.source, 'source required')
        result = fixture(args.case, args.kind, args.source)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'passed': True}))
