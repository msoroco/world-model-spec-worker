"""Synthetic source predicates for travel, visibility and parked motion."""
import argparse
import hashlib
import json
from pathlib import Path


LIFECYCLE = ['capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def classify(case_id):
    suffix = case_id.split('__')[-1]
    if suffix.startswith('parked_lamps_'):
        return 'parked'
    if suffix.startswith('controlled_'):
        return 'device'
    if suffix.startswith(('minutes_', 'target_reference_distance_ft_')):
        return 'boundary'
    raise ValueError('unknown exact case')


def measure(rows, case_id, source_path, source_sha):
    kind = classify(case_id)
    require(len(rows) == 600, '600 source frames required')
    before = None
    moving = 0
    parked_final = 0
    for index, row in enumerate(rows):
        require(row.get('video_frame') == index and
                type(row.get('native_frame')) is int and
                (before is None or row['native_frame'] > before),
                'original frame identity or order missing')
        before = row['native_frame']
        require(abs(row.get('time_s', -1) - index/20) < 1e-8,
                'source time changed')
        speed = row.get('ego_speed_mps') if kind == 'boundary' else row.get('speed_mps')
        require(type(speed) in (int, float) and speed >= 0,
                'speed source missing')
        moving += speed > .1
        if kind == 'parked' and index >= 500:
            parked_final += speed <= .1 and row.get('on_shoulder_readback') is True
    if kind == 'parked':
        met = moving >= 400 and parked_final == 100
        method = 'original 600-frame travel, mapped shoulder and final 100 stopped readbacks'
    else:
        met = moving >= 400
        method = 'original 600-frame paved-road travel readback'
    status = 'met' if met else 'not_met'
    return {'case_id': case_id, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {
                'status': status, 'method': method,
                'sources': [{'path': source_path, 'sha256': source_sha}],
                'moving_frames': moving, 'parked_final_frames': parked_final,
                'legal_verdict_claimed': False}},
            'maneuver_completed': met,
            'realized_observables': ({'moving_frames': {'value': moving,
                'unit': 'frames', 'method': 'synthetic diagnostic motion readback'},
                'parked_final_frames': {'value': parked_final,
                'unit': 'frames', 'method': 'synthetic diagnostic shoulder readback'}}
                if met else {}),
            'accepted': False, 'legal_verdict_claimed': False}


def fixture(case_id, kind, source):
    raw = Path(source).read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    source_sha = hashlib.sha256(raw).hexdigest()
    case_kind = classify(case_id)
    if kind == 'incomplete_motion':
        if case_kind == 'parked':
            for row in rows[500:]:
                row['on_shoulder_readback'] = False
        else:
            key = 'ego_speed_mps' if case_kind == 'boundary' else 'speed_mps'
            for row in rows:
                row[key] = 0.0
    if kind == 'missing_evidence':
        rows[200].pop('ego_speed_mps' if case_kind == 'boundary' else 'speed_mps')
    try:
        result = measure(rows, case_id, Path(source).name, source_sha)
    except ValueError as error:
        require(kind == 'missing_evidence' and 'speed source missing' in str(error),
                'unexpected fixture rejection')
        result = {'case_id': case_id, 'provenance_kind': 'synthetic_fixture',
                  'diagnostic_fixture': True,
                  'physical_checks': {'maneuver': {
                      'status': 'unverified', 'method': 'missing source rejection',
                      'sources': [{'path': Path(source).name, 'sha256': source_sha}],
                      'error': str(error)}},
                  'maneuver_completed': False, 'realized_observables': {},
                  'accepted': False, 'legal_verdict_claimed': False}
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    require(result['physical_checks']['maneuver']['status'] == expected,
            'fixture gave unexpected physical state')
    return result


def lifecycle(events):
    require(events == LIFECYCLE, 'saved processing precedes owner release')
    return {'events': events, 'exit_code': 0, 'original_capture_claimed': False}


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
            lifecycle(LIFECYCLE[:-2]+LIFECYCLE[-2:][::-1])
        except ValueError:
            pass
        else:
            raise AssertionError('premature saved processing accepted')
    else:
        require(args.source, 'source required')
        result = fixture(args.case, args.kind, args.source)
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'case_id': args.case, 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'passed': True}, sort_keys=True))
