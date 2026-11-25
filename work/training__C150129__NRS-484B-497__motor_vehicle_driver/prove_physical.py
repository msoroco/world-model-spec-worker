"""Source-shaped physical outcomes and ownership-order CPU proofs."""
import argparse
import json
from pathlib import Path

from parking_saved_measure import measure
from prove_parking_saved import fixture, wire

ASSIGNMENT = Path(__file__).resolve().parent.name
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
CASES = {'witness_1': True, 'witness_2': False,
         'exception_1_1': False, 'exception_1_2': True}


def physical(suffix, kind):
    if suffix not in CASES or kind not in ('complete_motion', 'incomplete_motion',
                                          'missing_evidence'):
        raise ValueError('Unknown exact case or fixture kind')
    packet, context = fixture(CASES[suffix])
    if kind == 'incomplete_motion':
        for frame in packet['frames'][300:]:
            frame['speed_mps'] = 2.0
    if kind == 'missing_evidence':
        packet['frames'].pop(300)
    try:
        metric = measure(wire(packet), wire(context))
    except ValueError as error:
        if kind != 'missing_evidence' or 'recording shorter than 30 seconds' not in str(error):
            raise
        status, realized = 'unverified', {}
        method = 'Original frame missing; source-bound 30-second motion cannot be assessed: ' + str(error)
    else:
        if kind == 'missing_evidence':
            raise ValueError('Missing original frame was accepted')
        rest = len(metric['fully_left_rest_candidate_frames'])
        status = 'met' if rest >= 100 else 'not_met'
        realized = {'fully_left_rest_candidate_frame_count': rest,
                    'permission_device_requested': CASES[suffix]}
        method = 'Original-frame footprint and speed yield a 100-frame engineering left-rest interval'
    if status != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                  'missing_evidence': 'unverified'}[kind]:
        raise ValueError('Physical fixture did not yield requested evidence status')
    return {'format': 'nrs-484b-497-physical-fixture-v1',
            'case_id': ASSIGNMENT + '__' + suffix, 'kind': kind,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status, 'method': method,
                                             'sources': ['vehicle-pose.jsonl',
                                                         'video_frames.jsonl', 'road-review.json',
                                                         'road.xodr']}},
            'maneuver_completed': status == 'met',
            'realized_observables': realized,
            'physical_or_legal_acceptance': False}


def lifecycle():
    def check_order(events):
        if events != EVENTS:
            raise ValueError('Saved processing precedes Native owner release or restoration')
        return True

    wrong = EVENTS[:4] + EVENTS[5:] + EVENTS[4:5]
    check_order(EVENTS)
    try:
        check_order(wrong)
    except ValueError:
        pass
    else:
        raise ValueError('Ownership-order negative was accepted')
    return {'format': 'nrs-484b-497-lifecycle-fixture-v1', 'events': EVENTS,
            'recorded_only': True, 'originals_preserved': True,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    value = lifecycle() if args.kind == 'lifecycle' else physical(args.case, args.kind)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'kind': args.kind,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'physical_or_legal_acceptance': False}))
