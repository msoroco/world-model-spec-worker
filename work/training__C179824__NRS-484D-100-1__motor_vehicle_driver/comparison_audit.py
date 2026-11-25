"""Independent original-source comparison for the controlled lamp pair."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = 'training__C179824__NRS-484D-100-1__motor_vehicle_driver'
CASES = (ASSIGNMENT + '__controlled_1', ASSIGNMENT + '__controlled_2')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, rel):
    path = (root / rel).resolve()
    require(root.resolve() in path.parents and path.is_file(),
            'Missing original comparison source: ' + rel)
    return path


def compare(left, right):
    """Compare source summaries without inventing a legal verdict."""
    require((left.get('case_id'), right.get('case_id')) == CASES,
            'Exact controlled case pair changed')
    require(left.get('source_kind') == right.get('source_kind') == 'native_saved_sample',
            'Original Native pair required')
    fixed = ('map_source_sha256', 'highway_source_sha256',
             'vehicle_class_source_sha256', 'device_content_source_sha256',
             'device_authority_source_sha256', 'device_placement_source_sha256',
             'device_timing_source_sha256', 'road_id', 'vehicle_blueprint_id',
             'device_governs_road_id', 'camera_profile', 'weather_request')
    for key in fixed:
        require(left.get(key) is not None and left.get(key) == right.get(key),
                'Comparison fixed source differs: ' + key)
    a, b = left.get('frames'), right.get('frames')
    require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 600,
            'Comparison requires two complete 600-frame traces')
    on, off, governed = 0, 0, 0
    for i, (x, y) in enumerate(zip(a, b)):
        for key in ('video_frame', 'time_s', 'road_id', 'device_active',
                    'camera_names'):
            require(x.get(key) == y.get(key),
                    'Comparison frame context differs: ' + key)
        require(x['video_frame'] == i and x['road_id'] == left['road_id'] and
                x['camera_names'] == list(CAMERAS),
                'Comparison source frame identity differs')
        require(abs(x.get('vehicle_x_m', 1e9) - y.get('vehicle_x_m', -1e9)) <= 0.5 and
                abs(x.get('speed_mps', 1e9) - y.get('speed_mps', -1e9)) <= 0.5,
                'Comparison route or speed changed')
        if x['device_active']:
            governed += 1
            on += x.get('headlamp_setting_on') is True and x.get('position_lamp_setting_on') is True
            off += y.get('headlamp_setting_on') is False and y.get('position_lamp_setting_on') is False
    require(governed >= 200 and on == off == governed,
            'Lamp-setting comparison variable did not separate')
    return {'format': 'c179824-lamp-pair-comparison-v1',
            'case_ids': list(CASES), 'frames': 600,
            'governed_frames': governed, 'lamp_on_frames': on,
            'lamp_off_frames': off,
            'fixed_sources': list(fixed),
            'deliberate_difference': 'lamp setting under same official device',
            'legal_verdict_claimed': False}


def load_original(root, case):
    result = json.loads(inside(root, 'result.json').read_text())
    require(result.get('case_id') == case and
            result.get('provenance_kind') == 'native_saved_sample' and
            result.get('diagnostic_fixture') is False,
            'Original Native comparison result missing')
    context_path = inside(root, 'lamp-context.json')
    context = json.loads(context_path.read_text())
    review = json.loads(inside(root, 'lamp-source-review.json').read_text())
    require(review.get('original_context_sha256') == sha(context_path) and
            review.get('review_kind') == 'original_source_review',
            'Original independent context review missing')
    summary = dict(context)
    summary.update({'case_id': case, 'source_kind': 'native_saved_sample',
                    'vehicle_blueprint_id': None,
                    'weather_request': context.get('daylight_weather_request'),
                    'camera_profile': list(CAMERAS), 'frames': []})
    for field, name in (
        ('highway_source_sha256', 'highway-review.json'),
        ('vehicle_class_source_sha256', 'vehicle-class-review.json'),
        ('device_content_source_sha256', 'device-content-review.json'),
        ('device_authority_source_sha256', 'device-authority-review.json'),
        ('device_placement_source_sha256', 'device-placement-review.json'),
        ('device_timing_source_sha256', 'device-timing-review.json')):
        path = inside(root, name)
        require(review.get(field) == sha(path),
                'Comparison review source changed: ' + name)
        source = json.loads(path.read_text())
        shared = source.get('shared_source_sha256')
        require(isinstance(shared, str) and len(shared) == 64 and
                all(c in '0123456789abcdef' for c in shared),
                'Independent shared source identity missing: ' + name)
        summary[field] = shared
    rows = [json.loads(line) for line in inside(root, 'vehicle-lamps.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in inside(root, 'video_frames.jsonl').read_text().splitlines()]
    require(len(rows) == len(mapping) == 600,
            'Original comparison frame count changed')
    for x, y in zip(rows, mapping):
        require(x['video_frame'] == y['video_frame'] and
                x['native_frame'] == y['native_frame'] and
                x['camera_native_frames'] == y['camera_native_frames'],
                'Original comparison frame map changed')
        require(set(x['camera_native_frames']) == set(CAMERAS),
                'Original comparison camera profile changed')
        summary['frames'].append({
            'video_frame': x['video_frame'], 'time_s': x['time_s'],
            'road_id': x['road_id'], 'device_active': x['device_active'],
            'camera_names': list(CAMERAS),
            'vehicle_x_m': x['vehicle_xy_m'][0], 'speed_mps': x['speed_mps'],
            'headlamp_setting_on': x['headlamp_setting_on'],
            'position_lamp_setting_on': x['position_lamp_setting_on']})
    summary['vehicle_blueprint_id'] = rows[0]['vehicle_blueprint_id']
    return summary


def audit(args):
    left_root, right_root = Path(args.on_attempt).resolve(), Path(args.off_attempt).resolve()
    left = load_original(left_root, CASES[0])
    right = load_original(right_root, CASES[1])
    result = compare(left, right)
    result['source_sha256'] = {
        'on_trace': sha(inside(left_root, 'vehicle-lamps.jsonl')),
        'off_trace': sha(inside(right_root, 'vehicle-lamps.jsonl')),
        'on_result': sha(inside(left_root, 'result.json')),
        'off_result': sha(inside(right_root, 'result.json'))}
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2) + '\n')
    return result


def self_test(negative):
    common = {'source_kind': 'native_saved_sample', 'map_source_sha256': 'map',
              'highway_source_sha256': 'highway',
              'vehicle_class_source_sha256': 'class',
              'device_content_source_sha256': 'content',
              'device_authority_source_sha256': 'authority',
              'device_placement_source_sha256': 'placement',
              'device_timing_source_sha256': 'timing', 'road_id': '1',
              'vehicle_blueprint_id': 'vehicle.tesla.model3',
              'device_governs_road_id': '1',
              'camera_profile': list(CAMERAS), 'weather_request': 'ClearNoon'}
    def case(index, on):
        return dict(common, case_id=CASES[index], frames=[{
            'video_frame': i, 'time_s': i/20, 'road_id': '1',
            'device_active': i >= 100, 'camera_names': list(CAMERAS),
            'vehicle_x_m': -70 + i*.15, 'speed_mps': 3,
            'headlamp_setting_on': on, 'position_lamp_setting_on': on}
            for i in range(600)])
    left, right = case(0, True), case(1, False)
    if negative:
        right['device_authority_source_sha256'] = 'another-authority'
        compare(left, right)
        raise AssertionError('Changed governing source accepted')
    result = compare(left, right)
    for field, value in (('map_source_sha256', 'another-map'),
                         ('weather_request', 'HardRainNoon')):
        bad = json.loads(json.dumps(right))
        bad[field] = value
        try:
            compare(left, bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed fixed condition accepted: '+field)
    return dict(result, original_capture_attested=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--on-attempt')
    parser.add_argument('--off-attempt')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(self_test(args.negative) if args.self_test else audit(args),
                     indent=2))
