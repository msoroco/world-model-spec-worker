"""Independent saved-source and controlled-comparison checks for C179789.

This audit verifies provenance and declared changes. It never makes a legal or
physical-acceptance decision from synthetic or unreviewed sources.
"""

import hashlib
import json
import math
import argparse
from pathlib import Path

ASSIGNMENT = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver'
EXACT_CASES = {ASSIGNMENT + '__' + suffix for suffix in (
    'dry_open_traffic', 'wet_same_traffic', 'narrow_same_traffic',
    'dense_traffic', 'low_visibility', 'ice_or_snow')}
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
SOURCE_NAMES = ('road_context.json', 'condition_history.jsonl',
                'video_frames.jsonl')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path):
    return json.loads(path.read_text())


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit_delivery(attempt, analysis_path):
    attempt = Path(attempt)
    result = _json(attempt / 'result.json')
    analysis = _json(Path(analysis_path))
    config = _json(attempt / 'config.json')
    case = config['selected_case_id']
    if case not in EXACT_CASES or case != result.get('case_id') or case != analysis.get('case_id'):
        raise ValueError('Exact saved case join failed')
    if result.get('physical_acceptance_claimed') is not False or analysis.get('physical_acceptance_claimed') is not False:
        raise ValueError('Unreviewed physical acceptance claimed')
    if (result.get('measured_values', {}).get('reasonable_or_proper_judgment') != 'unresolved'
            or analysis.get('legal_conclusion') != 'unresolved'):
        raise ValueError('Unsupported reasonable-or-proper conclusion')
    sources = result.get('source_hashes')
    if sources != analysis.get('source_report', {}).get('sources') or not isinstance(sources, dict):
        raise ValueError('Saved source-hash inventories differ')
    for name, digest in sources.items():
        rel = Path(name)
        path = (attempt / rel).resolve()
        if rel.is_absolute() or '..' in rel.parts or not path.is_relative_to(attempt.resolve()):
            raise ValueError('Unsafe saved source path')
        if not path.is_file() or _sha(path) != digest:
            raise ValueError('Saved original source changed: ' + name)
    if not set(SOURCE_NAMES).issubset(sources):
        raise ValueError('Missing required condition source hashes')
    capture = attempt / 'capture/evidence.jsonl'
    if not capture.is_file() or _sha(capture) != result.get('capture_evidence_sha256'):
        raise ValueError('Saved capture evidence changed')
    for camera in CAMERAS:
        if camera not in result.get('video_references', []) or not (attempt / camera).is_file():
            raise ValueError('Saved original camera missing: ' + camera)
    rows = _rows(attempt / 'condition_history.jsonl')
    frames = _rows(attempt / 'video_frames.jsonl')
    channel = _rows(attempt / 'speed-channel.jsonl')
    samples = analysis['source_report']['samples']
    if len(rows) < 2 or not (len(rows) == len(frames) == len(channel) == len(samples)):
        raise ValueError('Original frame or speed-channel count differs')
    target = config['condition_target']
    for index, (row, frame, speed_row, sample) in enumerate(zip(rows, frames, channel, samples)):
        if (frame.get('video_frame') != index or frame.get('carla_frame') != row.get('frame')
                or sample.get('frame') != row.get('frame') or sample.get('time_s') != row.get('time_s')):
            raise ValueError('Independent original frame join failed')
        velocity = row.get('ego_velocity_mps')
        if not isinstance(velocity, list) or len(velocity) != 3 or any(
                type(value) not in (int, float) or not math.isfinite(value) for value in velocity):
            raise ValueError('Original Native velocity invalid')
        speed = math.sqrt(sum(value * value for value in velocity))
        if (abs(speed_row.get('value', -1) - speed) > 1e-9
                or abs(sample.get('ego_speed_mps', -1) - speed) > 1e-9
                or speed_row.get('time_s') != row.get('time_s')):
            raise ValueError('Derived speed differs from original velocity')
        if row.get('surface') != target['surface']:
            raise ValueError('Surface target differs from original frame')
        for key, value in (('lane_width_m', row['lane_width_m']),
                           ('longitudinal_body_gap_m', row['surrounding_traffic'][0]['longitudinal_body_gap_m']),
                           ('sight_distance_m', row['sight_distance_m']),
                           ('precipitation_percent', row['precipitation_percent'])):
            if not target[key][0] <= value <= target[key][1]:
                raise ValueError('Condition target differs from original frame: ' + key)
        for key in ('fog_density_percent', 'fog_distance_m'):
            if key in target:
                value = row[key]
                if sample.get(key) != value or not target[key][0] <= value <= target[key][1]:
                    raise ValueError('Fog target differs from original frame: ' + key)
    matched = {check['target']: check['matched'] for check in result.get('target_checks', [])}
    if any(not matched.get(key, False) for key in (*target.keys(), 'sampled_peak_speed_mps')):
        raise ValueError('Saved condition or speed target did not match')
    return {'format': 'worker-c179789-independent-delivery-audit', 'case_id': case,
            'passed': True, 'source_hashes': sources, 'frame_count': len(rows),
            'camera_sha256': {name: _sha(attempt / name) for name in CAMERAS},
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


def audit_comparison(attempts):
    """Check declared changes in all six exact constructions."""
    if set(attempts) != {'dry_open_traffic', 'wet_same_traffic', 'dense_traffic',
                         'narrow_same_traffic', 'low_visibility', 'ice_or_snow'}:
        raise ValueError('Six exact controlled comparison members required')
    docs = {}
    for suffix, root in attempts.items():
        root = Path(root)
        config = _json(root / 'config.json')
        road = _json(root / 'road_packet.json')
        if config['selected_case_id'] != ASSIGNMENT + '__' + suffix or road['case_id'] != config['selected_case_id']:
            raise ValueError('Controlled comparison case join failed')
        docs[suffix] = (config, road, _json(root / 'surface_packet.json'))
    dry, wet, dense, narrow, low, ice = (docs[key] for key in (
        'dry_open_traffic', 'wet_same_traffic', 'dense_traffic', 'narrow_same_traffic', 'low_visibility', 'ice_or_snow'))
    for other in (wet, dense, low, ice):
        for key in ('native_map_id', 'road_id', 'lane_id', 'ego_spawn',
                    'ego_target_speed_mps', 'vehicle_blueprint_id', 'lead_blueprint_id'):
            if other[1][key] != dry[1][key]:
                raise ValueError('Undeclared fixed road or ego change: ' + key)
    for key in ('native_map_id', 'lane_id', 'ego_target_speed_mps',
                'vehicle_blueprint_id', 'lead_blueprint_id'):
        if narrow[1][key] != dry[1][key]:
            raise ValueError('Undeclared narrow vehicle or control change: ' + key)
    for other in (wet, dense, narrow, low, ice):
        for key in ('rate_hz', 'duration_s', 'cameras', 'requested_speed_mps'):
            if other[0][key] != dry[0][key]:
                raise ValueError('Undeclared fixed capture change: ' + key)
    if wet[1]['lead_spawn'] != dry[1]['lead_spawn'] or wet[1]['lead_target_speed_mps'] != dry[1]['lead_target_speed_mps']:
        raise ValueError('Wet case changed fixed traffic')
    if wet[2]['surface'] != 'wet' or dry[2]['surface'] != 'dry' or wet[1]['weather_profile'] == dry[1]['weather_profile']:
        raise ValueError('Wet case lacks declared surface/weather change')
    if dense[2] != dry[2] or dense[1]['weather_profile'] != dry[1]['weather_profile']:
        raise ValueError('Dense case changed fixed surface/weather')
    if dense[1]['lead_spawn'] == dry[1]['lead_spawn'] or dense[1]['lead_target_speed_mps'] == dry[1]['lead_target_speed_mps']:
        raise ValueError('Dense case lacks declared traffic change')
    for key in ('lead_spawn', 'lead_target_speed_mps'):
        if low[1][key] != dry[1][key]:
            raise ValueError('Low-visibility case changed fixed traffic')
    if low[2] != dry[2]:
        raise ValueError('Low-visibility case changed fixed surface')
    dry_weather, low_weather = dry[1]['weather_profile'], low[1]['weather_profile']
    for key in ('cloudiness', 'precipitation', 'wetness', 'sun_altitude_angle'):
        if low_weather[key] != dry_weather[key]:
            raise ValueError('Low-visibility case changed fixed weather: ' + key)
    if (low_weather['fog_density'] == dry_weather['fog_density'] or
            low_weather['fog_distance'] == dry_weather['fog_distance'] or
            low[0]['condition_target'].get('fog_density_percent') != [70, 90] or
            low[0]['condition_target'].get('fog_distance_m') != [10, 30]):
        raise ValueError('Low-visibility case lacks declared fog change')
    for key in ('lead_spawn', 'lead_target_speed_mps'):
        if ice[1][key] != dry[1][key]:
            raise ValueError('Ice/snow case changed fixed traffic')
    if (ice[2]['surface'] != 'ice_or_snow' or
            ice[2]['road_id'] != ice[1]['road_id'] or
            ice[1]['weather_profile'] == dry_weather or
            ice[0]['condition_target']['precipitation_percent'] != [70, 90]):
        raise ValueError('Ice/snow case lacks declared surface/weather change')
    def relative_gap(packet):
        return [packet['lead_spawn'][axis] - packet['ego_spawn'][axis]
                for axis in ('x', 'y', 'z')]
    if (narrow[2]['surface'] != dry[2]['surface'] or
            narrow[2]['road_id'] != narrow[1]['road_id'] or
            narrow[1]['road_id'] == dry[1]['road_id'] or
            narrow[1]['ego_spawn'] == dry[1]['ego_spawn'] or
            narrow[1]['weather_profile'] != dry[1]['weather_profile'] or
            relative_gap(narrow[1]) != relative_gap(dry[1]) or
            narrow[1]['lead_target_speed_mps'] != dry[1]['lead_target_speed_mps']):
        raise ValueError('Narrow case changed fixed surface, weather or traffic')
    if (narrow[0]['condition_target']['lane_width_m'] != [2.5, 2.9]
            or dry[0]['condition_target']['lane_width_m'] != [3, 4]):
        raise ValueError('Narrow case lacks declared lane-width change')
    return {'format': 'worker-c179789-independent-comparison-audit', 'passed': True,
            'cases': [ASSIGNMENT + '__' + key for key in attempts],
            'physical_realization_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt')
    parser.add_argument('--analysis')
    parser.add_argument('--dry')
    parser.add_argument('--wet')
    parser.add_argument('--dense')
    parser.add_argument('--narrow')
    parser.add_argument('--low')
    parser.add_argument('--ice')
    args = parser.parse_args()
    if args.attempt and args.analysis and not any((args.dry, args.wet, args.dense, args.narrow, args.low, args.ice)):
        receipt = audit_delivery(args.attempt, args.analysis)
    elif all((args.dry, args.wet, args.dense, args.narrow, args.low, args.ice)) and not any((args.attempt, args.analysis)):
        receipt = audit_comparison({'dry_open_traffic': args.dry,
                                    'wet_same_traffic': args.wet,
                                    'dense_traffic': args.dense,
                                    'narrow_same_traffic': args.narrow,
                                    'low_visibility': args.low,
                                    'ice_or_snow': args.ice})
    else:
        parser.error('Supply an attempt and analysis, or six controlled source roots')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
