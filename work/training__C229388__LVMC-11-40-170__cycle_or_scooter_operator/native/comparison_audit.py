"""Independently compare two rack-supported parking positions."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_parking import measure

AID = 'training__C229388__LVMC-11-40-170__cycle_or_scooter_operator'
FIXED = ('device_subtype', 'device_actor_id', 'operator_actor_id', 'rack_actor_id',
    'rack_support_confirmed', 'rack_polygon_xy_m', 'sidewalk_polygon_xy_m',
    'roadway_polygon_xy_m', 'curb_polyline_xy_m', 'pedestrian_corridor_polygon_xy_m',
    'device_subtype_source', 'rack_support_source', 'sidewalk_geometry_source',
    'roadway_geometry_source', 'curb_geometry_source', 'pedestrian_corridor_source',
    'operator_join_source', 'parking_state_source')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left, right, diagnostic=False, negative=False):
    left, right = Path(left), Path(right)
    first, second = measure(left), measure(right)
    context = [json.loads((root / 'parking_context.json').read_text()) for root in (left, right)]
    expected = 'synthetic_diagnostic' if diagnostic else 'original_source_review'
    if any(item['review_kind'] != expected for item in context):
        raise ValueError('Original source comparison review absent')
    if context[0].get('case_id') != AID + '__probe_01' or context[1].get('case_id') != AID + '__probe_02':
        raise ValueError('Parking comparison case identity differs')
    if negative:
        context[1]['rack_support_confirmed'] = False
    if any(context[0].get(key) != context[1].get(key) for key in FIXED):
        raise ValueError('Fixed rack, pedestrian corridor, device or operator context differs')
    if context[0]['rack_support_confirmed'] is not True:
        raise ValueError('Same supporting rack source review missing')
    if first['rest_frame_count'] != 600 or second['rest_frame_count'] != 600:
        raise ValueError('Full stationary parking comparison missing')
    if first['rack_intersection_frame_count'] != 600 or second['rack_intersection_frame_count'] != 600:
        raise ValueError('Both parked devices must intersect the same reviewed rack')
    if first['pedestrian_corridor_intersection_frame_count'] != 0 or second['pedestrian_corridor_intersection_frame_count'] != 600:
        raise ValueError('Measured pedestrian corridor contrast absent')
    return {'format': 'worker-lvmc-rack-corridor-comparison-v1',
        'comparison_id': AID + '__rack_corridor_position',
        'case_ids': [AID + '__probe_01', AID + '__probe_02'], 'passed': True,
        'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False, 'fixed_conditions_checked': list(FIXED),
        'deliberate_difference': 'Native parked-device footprint position relative to the same pedestrian corridor',
        'source_sha256': {'probe_01': {name: sha(left / name) for name in
            ('video_frames.jsonl', 'native_parking_trace.jsonl', 'parking_context.json')},
            'probe_02': {name: sha(right / name) for name in
            ('video_frames.jsonl', 'native_parking_trace.jsonl', 'parking_context.json')}},
        'measurements': {'probe_01': first, 'probe_02': second}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(compare(args.left, args.right, args.diagnostic, args.negative_selftest), sort_keys=True))


if __name__ == '__main__':
    main()
