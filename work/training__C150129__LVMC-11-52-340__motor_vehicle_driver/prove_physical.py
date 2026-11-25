"""CPU physical outcome and lifecycle fixtures for municipal parking cases."""
import argparse
import json
from pathlib import Path

from parking_measure import ASSIGNMENT, measure


EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def fixture(case, kind):
    if case not in (1, 2):
        raise ValueError('Unknown municipal parking case')
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    x = 20.0 if case == 1 else 0.0
    frames = [{'video_frame': i, 'native_frame': i + 1000, 'time_s': i / 20,
               'vehicle_id': 'ego', 'vehicle_xy_m': [x, -5.2], 'yaw_rad': 0.0,
               'bbox_half_length_m': 2.0, 'bbox_half_width_m': .8,
               'speed_mps': (0.0 if kind == 'complete_motion' and 200 <= i < 500 else 2.0)}
              for i in range(600)]
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
              'vehicle_id': 'ego', 'frames': frames}
    inventory = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
                 'city_street_source_id': 'synthetic-city-street',
                 'council_designation_source_id': 'synthetic-council-record',
                 'space_id': 'city-space-01', 'posting_space_id': 'city-space-01',
                 'posting_or_marking_source_id': 'synthetic-posting',
                 'subject_status_source_id': 'synthetic-status',
                 'subject_city_vehicle': False,
                 'space_polygon_xy_m': [[-6, -7], [6, -7], [6, -3.5], [-6, -3.5]]}
    if kind == 'missing_evidence':
        frames.pop(300)
    try:
        metric = measure(json.dumps(packet).encode(), json.dumps(inventory).encode())
    except ValueError as error:
        if kind != 'missing_evidence' or str(error) != '600 original frames required':
            raise
        status, completed, observables = 'unverified', False, {}
        sources = ['vehicle-poses.jsonl', 'parking-inventory.json']
        explanation = 'original frame missing: ' + str(error)
    else:
        if kind == 'missing_evidence':
            raise ValueError('Missing original frame was accepted')
        stationary = metric['stationary_proxy_frames']
        inside = metric['occupied_and_stationary_proxy_frames']
        requested_inside = case == 2
        completed = len(stationary) >= 100 and bool(inside) == requested_inside
        status = 'met' if completed else 'not_met'
        observables = {'stationary_proxy_frame_count': len(stationary),
                       'inside_city_space_stationary_frame_count': len(inside),
                       'target_inside_city_space': requested_inside}
        sources = ['vehicle-poses.jsonl', 'parking-inventory.json',
                   'video_frames.jsonl', 'review.json']
        explanation = '600-frame source-shaped full-footprint occupancy and 100-frame engineering rest interval'
    return {'format': 'c150129-cpu-physical-fixture',
            'case_id': ASSIGNMENT + '__controlled_' + str(case),
            'kind': kind, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status, 'method': explanation,
                                             'sources': sources}},
            'maneuver_completed': completed, 'realized_observables': observables,
            'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False}


def lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native owner release or restoration')
    return {'format': 'c150129-cpu-lifecycle-proof', 'events': events,
            'originals_preserved': True, 'saved_processing_recorded_only': True,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=int, required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        result = lifecycle(EVENTS)
        try:
            lifecycle(EVENTS[:4] + EVENTS[5:] + EVENTS[4:5])
        except ValueError:
            pass
        else:
            raise ValueError('Out-of-order lifecycle was accepted')
    else:
        result = fixture(args.case, args.kind)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        if result['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('Physical fixture result differs')
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'physical_or_legal_acceptance': False}, sort_keys=True))


if __name__ == '__main__':
    main()
