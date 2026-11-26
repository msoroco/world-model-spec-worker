"""Independent raw separator comparison; legal authority is reviewed later."""
import argparse
import json
import tempfile
from pathlib import Path

from measure_separator import measure


def compare(stay, cross):
    for item in (stay, cross):
        if item.get('format') != 'c245532-solid-white-separator-raw-geometry-v1':
            raise ValueError('Missing exact original separator measurement')
        if item.get('frame_count') != 600 or item.get('rate_hz') != 20:
            raise ValueError('Original comparison duration or rate differs')
        if item.get('legal_verdict_claimed') is not False or item.get('physical_acceptance_claimed') is not False:
            raise ValueError('Unsupported legal or physical claim')
        if set(item.get('camera_video_sha256', {})) != {
            'overview', 'approach', 'reference_corner', 'driver_reference'
        }:
            raise ValueError('Original four-camera source incomplete')
        if not all(item.get('source_sha256', {}).get(name) for name in (
            'separator-context.json', 'native-motion.jsonl', 'video_frames.jsonl'
        )):
            raise ValueError('Original source hashes incomplete')
    if stay['separator'] != cross['separator']:
        raise ValueError('Fixed solid-white separator differs')
    if stay['source_context_review'] != cross['source_context_review']:
        raise ValueError('Fixed controlled-access source context differs')
    if stay['body_straddle_frame_count'] != 0 or stay['first_traffic_side_center_frame'] is not None:
        raise ValueError('Stay-side target was not measured')
    if cross['body_straddle_frame_count'] <= 0 or cross['first_traffic_side_center_frame'] is None:
        raise ValueError('Cross-side target was not measured')
    return {
        'format': 'c245532-separator-comparison-audit-v1',
        'raw_difference_observed': True,
        'fixed_separator_and_source_context': True,
        'source_context_review_pending': stay['source_context_review_pending'] or cross['source_context_review_pending'],
        'legal_verdict_claimed': False,
        'physical_acceptance_claimed': False,
    }


def compare_emergency(clear, obstructed):
    for item in (clear, obstructed):
        if item.get('format') != 'c245532-solid-white-separator-raw-geometry-v1' or item.get('frame_count') != 600 or item.get('rate_hz') != 20:
            raise ValueError('Missing exact emergency candidate source measurement')
        if item.get('legal_verdict_claimed') is not False or item.get('physical_acceptance_claimed') is not False:
            raise ValueError('Unsupported legal or physical claim')
        if set(item.get('camera_video_sha256', {})) != {'overview','approach','reference_corner','driver_reference'}:
            raise ValueError('Original four-camera source incomplete')
    if clear['separator'] != obstructed['separator'] or clear['source_context_review'] != obstructed['source_context_review']:
        raise ValueError('Fixed emergency comparison context differs')
    for key in ('first_body_straddle_frame','first_traffic_side_center_frame','body_straddle_frame_count','native_lane_ids_seen'):
        if clear.get(key) != obstructed.get(key):
            raise ValueError('Fixed crossing motion differs: '+key)
    if clear.get('emergency_obstruction_present') is not False or obstructed.get('emergency_obstruction_present') is not True:
        raise ValueError('Stopped obstruction comparison variable not measured')
    if obstructed.get('minimum_obstruction_center_distance_m') is None or clear.get('minimum_obstruction_center_distance_m') is not None:
        raise ValueError('Obstruction separation source differs')
    return {'format':'c245532-emergency-candidate-comparison-v1',
        'stopped_obstruction_delta_observed':True,'fixed_crossing_geometry_observed':True,
        'legal_necessity_claimed':False,'physical_acceptance_claimed':False}


def self_test():
    from prove_saved import fixture
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        stay, cross = root/'stay', root/'cross'
        fixture(stay, False, reviewed=False)
        fixture(cross, True, reviewed=False)
        a, b = measure(stay), measure(cross)
        passed = compare(a, b)
        assert passed['source_context_review_pending']
        changed = dict(b, separator={**b['separator'], 'color': 'yellow'})
        try:
            compare(a, changed)
        except ValueError as error:
            assert 'separator differs' in str(error)
        else:
            raise AssertionError('Changed fixed separator accepted')
        changed = dict(b, camera_video_sha256={})
        try:
            compare(a, changed)
        except ValueError as error:
            assert 'four-camera' in str(error)
        else:
            raise AssertionError('Missing camera source accepted')
        emergency=root/'emergency'
        fixture(emergency,True,reviewed=False,obstruction=True)
        c=measure(emergency)
        emergency_result=compare_emergency(b,c)
        changed=dict(c,first_body_straddle_frame=-1)
        try:compare_emergency(b,changed)
        except ValueError as error:assert 'Fixed crossing motion differs' in str(error)
        else:raise AssertionError('Changed crossing motion accepted')
        return dict(passed, synthetic_test_passed=True,
                    changed_separator_rejected=True, missing_camera_rejected=True,
                    emergency_candidate=emergency_result,changed_emergency_motion_rejected=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stay', type=Path)
    parser.add_argument('--cross', type=Path)
    parser.add_argument('--emergency-clear',type=Path)
    parser.add_argument('--emergency-obstructed',type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        value = self_test()
    else:
        if args.emergency_clear and args.emergency_obstructed:
            value=compare_emergency(json.loads(args.emergency_clear.read_text()),
                json.loads(args.emergency_obstructed.read_text()))
        else:
            if args.stay is None or args.cross is None:
                parser.error('Both original measurement files are required')
            value = compare(json.loads(args.stay.read_text()), json.loads(args.cross.read_text()))
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
