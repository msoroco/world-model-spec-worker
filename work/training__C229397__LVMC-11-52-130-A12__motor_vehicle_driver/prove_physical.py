"""Source-shaped CPU motion and Native-owner lifecycle fixtures for crosswalk cases."""
import argparse
import json
from pathlib import Path

from crosswalk_measure import ASSIGNMENT, measure


EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
GAPS = {'controlled_1': 12.0, 'boundary_20ft': 6.096,
        'controlled_2': 3.0, 'stop_near': 3.0, 'stand_near': 3.0,
        'traffic_conflict_near': 3.0, 'law_compliance_near': 3.0,
        'police_direction_near': 3.0, 'device_direction_near': 3.0}


def fixture(suffix, kind):
    if suffix not in GAPS or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown crosswalk fixture')
    gap = GAPS[suffix]
    frames = [{'video_frame': i, 'native_frame': i + 1000, 'time_s': i / 20,
               'vehicle_id': 'ego', 'vehicle_xy_m': [-gap - 2.0, 0.0],
               'yaw_rad': 0.0, 'bbox_half_length_m': 2.0,
               'bbox_half_width_m': .8,
               'speed_mps': 0.0 if kind != 'incomplete_motion' and 200 <= i < 500 else 2.0}
              for i in range(600)]
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
              'vehicle_id': 'ego', 'frames': frames}
    inventory = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
                 'jurisdiction_source_id': 'synthetic-jurisdiction',
                 'marked_crosswalk_source_id': 'synthetic-paint-review',
                 'crosswalk_extent_source_id': 'synthetic-extent-review',
                 'responsible_person_source_id': 'synthetic-person-review',
                 'traffic_conflict_review_source_id': 'synthetic-traffic-review',
                 'law_compliance_review_source_id': 'synthetic-law-review',
                 'directions_review_source_id': 'synthetic-directions-review',
                 'crosswalk_rect_xyxy_m': [0.0, 2.0, -1.0, 1.0]}
    if kind == 'missing_evidence':
        frames.pop(300)
    try:
        metric = measure(json.dumps(packet).encode(), json.dumps(inventory).encode())
    except ValueError as error:
        if kind != 'missing_evidence' or str(error) != '600 original frames required':
            raise
        status, completed, observables = 'unverified', False, {}
        method = 'missing original frame rejected by source-bound distance measure'
    else:
        if kind == 'missing_evidence':
            raise ValueError('Missing original frame was accepted')
        spans = [span for span in metric['halt_proxy_spans']
                 if span['sampled_duration_s'] >= 5 and
                 abs(span['minimum_body_distance_m'] - gap) <= 1.0]
        completed = bool(spans)
        status = 'met' if completed else 'not_met'
        observables = {'sampled_halt_spans': metric['halt_proxy_spans'],
                       'minimum_body_gap_m': min(metric['body_to_crosswalk_m_by_frame'])}
        method = '600-frame source-shaped body gap and at least five-second sampled halt proxy'
    return {'format': 'c229397-cpu-physical-fixture',
            'case_id': ASSIGNMENT + '__' + suffix, 'kind': kind,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_checks': {'maneuver': {'status': status, 'method': method,
                                             'sources': ['vehicle-poses.jsonl',
                                                         'crosswalk-inventory.json',
                                                         'video_frames.jsonl', 'review.json']}},
            'maneuver_completed': completed, 'realized_observables': observables,
            'legal_acceptance_claimed': False, 'physical_acceptance_claimed': False}


def lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native owner release or restoration')
    return {'format': 'c229397-cpu-lifecycle-proof', 'events': events,
            'originals_preserved': True, 'saved_processing_recorded_only': True,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
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
            raise ValueError('Out-of-order owner lifecycle accepted')
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
