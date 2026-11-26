"""Independent source-bound comparison of two exact selected attempts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('config.json', 'road.xodr', 'road-context.json',
           'native-feature-source.jsonl', 'video_frames.jsonl', 'trace.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def load(directory, expected_case):
    directory = Path(directory)
    for name in SOURCES:
        if not (directory / name).is_file():
            raise ValueError('Missing original comparison source: ' + name)
    config = json.loads((directory / 'config.json').read_text())
    road = json.loads((directory / 'road-context.json').read_text())
    feature = rows(directory / 'native-feature-source.jsonl')
    frame_map = rows(directory / 'video_frames.jsonl')
    trace = rows(directory / 'trace.jsonl')
    if config.get('selected_case_id') != expected_case or len(feature) != 600 or len(frame_map) != 600 or len(trace) != 600:
        raise ValueError('Exact case or full 600-frame source is missing')
    for index, (item, mapping, pose) in enumerate(zip(feature, frame_map, trace)):
        if (item.get('frame') != index or item.get('native_frame') != mapping.get('native_frame')
                or mapping.get('video_frame') != index or pose.get('frame') != mapping.get('carla_frame')
                or item.get('camera_frame_ids') != {camera: index for camera in CAMERAS}):
            raise ValueError('Original frame or camera join differs')
    hashes = {name: sha(directory / name) for name in SOURCES}
    left_frames = [item['frame'] for item in feature if item['ego_body_min_signed_m'] < 0]
    return {'config': config, 'road': road, 'feature': feature,
            'left_frames': left_frames, 'hashes': hashes}


def phases(config):
    return [(item['name'], item['first_frame'], item['last_frame'], item['target_speed_mps'])
            for item in config['control_phases']]


def requested_left(config):
    return any(item['target_lane_id'] != config['ego_lane_id']
               for item in config['control_phases'])


def compare(comparison_id, left_path, right_path):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison = next((item for item in plan['comparisons']
                       if item['comparison_id'] == comparison_id), None)
    if comparison is None or len(comparison['case_ids']) != 2:
        raise ValueError('Unknown exact two-case comparison')
    left = load(left_path, comparison['case_ids'][0])
    right = load(right_path, comparison['case_ids'][1])
    a, b = left['config'], right['config']
    for key in ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'cameras',
                'required_atoms', 'source_packets'):
        if a.get(key) != b.get(key):
            raise ValueError('Fixed comparison configuration differs: ' + key)
    if phases(a) != phases(b):
        raise ValueError('Fixed controller phase schedule differs')
    if left['road']['feature_kind'] != right['road']['feature_kind']:
        raise ValueError('Fixed crest or curve feature differs')
    suffix = comparison_id.rsplit('__', 1)[-1]
    if suffix in ('crest_left_side', 'curve_left_side'):
        if left['hashes']['road.xodr'] != right['hashes']['road.xodr']:
            raise ValueError('Fixed two-way road geometry differs')
        if left['road']['directionality'] != 'two_way' or right['road']['directionality'] != 'two_way':
            raise ValueError('Two-way comparison directionality differs')
        if requested_left(a) or not requested_left(b):
            raise ValueError('Declared left-of-centre controller difference missing')
        if left['left_frames'] or not right['left_frames']:
            raise ValueError('Measured body-occupancy contrast absent')
        if any(item['other_vehicle_route_direction'] != 'opposing'
               for item in left['feature'] + right['feature']):
            raise ValueError('Opposite-route participant source differs')
    elif suffix in ('crest_one_way_exception', 'curve_one_way_exception'):
        if not requested_left(a) or not requested_left(b):
            raise ValueError('Fixed requested leftward trajectory absent')
        if (left['road']['directionality'], right['road']['directionality']) != ('two_way', 'one_way'):
            raise ValueError('Declared roadway-directionality difference absent')
        if (left['feature'][0]['other_vehicle_route_direction'],
                right['feature'][0]['other_vehicle_route_direction']) != ('opposing', 'same'):
            raise ValueError('Declared participant-direction difference absent')
        if not left['left_frames'] or not right['left_frames']:
            raise ValueError('Leftward source trajectory is absent')
    else:
        raise ValueError('Unreviewed comparison branch')
    if left['road'].get('legal_highway_authority_verified') or right['road'].get('legal_highway_authority_verified'):
        raise ValueError('CPU fixture claims legal highway designation')
    return {'format': 'worker-c230259-213-2a-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'passed': True, 'source_hashes': [left['hashes'], right['hashes']],
            'measured_left_body_frames': [len(left['left_frames']), len(right['left_frames'])],
            'fixed_conditions_checked': comparison['fixed_conditions'],
            'deliberate_differences_checked': comparison['deliberate_differences'],
            'legal_or_physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = compare(args.comparison, args.left, args.right)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True}))
