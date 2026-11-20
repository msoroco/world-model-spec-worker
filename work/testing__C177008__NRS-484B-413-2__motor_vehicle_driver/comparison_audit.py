"""Independent CPU comparison of original diagnostic source packets.

The inputs are saved attempt evidence directories. This checks source isolation and
measured signal distance; synthetic packets cannot prove physical or legal results.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_sources(root):
    root = Path(root)
    drive = lines(root / 'drive_history.jsonl')
    body = lines(root / 'body_history.jsonl')
    capture = lines(root / 'capture/evidence.jsonl')
    route = json.loads((root / 'route_context.json').read_text())
    provenance = json.loads((root.parent / 'acquisition-provenance.json').read_text()) if (root.parent / 'acquisition-provenance.json').exists() else None
    require(len(drive) >= 3 and len(drive) == len(body) == len(capture), 'Source frame counts differ')
    require([row['frame'] for row in drive] == [row['frame'] for row in body], 'Body frame join changed')
    require([row['frame'] for row in drive] == [row['original_frame'] for row in capture], 'Capture frame join changed')
    require(all(row['right_indicator'] == bool(row['ego_light_mask'] & 16) for row in drive), 'Right indicator lamp-mask conflict')
    require(route['turn_onset_frame'] == drive[-1]['frame'], 'Turn-onset frame differs from retained source')
    require(all(drive[i]['time_s'] > drive[i-1]['time_s'] for i in range(1, len(drive))), 'Source time is not increasing')
    weather = [row['world']['weather'] for row in capture]
    require(all(value == weather[0] for value in weather), 'Weather changed during diagnostic capture')
    hashes = {name: digest(root / name) for name in ('road.xodr', 'drive_history.jsonl', 'body_history.jsonl', 'route_context.json', 'capture/evidence.jsonl')}
    return {'root': str(root), 'drive': drive, 'body': body, 'route': route,
            'weather': weather[0], 'hashes': hashes, 'provenance': provenance}


def distance_and_start(rows):
    index = len(rows) - 1
    require(rows[index]['right_indicator'], 'Right signal is off at turn onset')
    while index > 0 and rows[index-1]['right_indicator']:
        index -= 1
    distance = sum(math.dist(rows[i-1]['ego_position_xy_m'], rows[i]['ego_position_xy_m'])
                   for i in range(index + 1, len(rows)))
    return distance, rows[index]['frame']


def audit(comparison_id, left, right):
    require(left['hashes']['road.xodr'] == right['hashes']['road.xodr'], 'Authored road map changed')
    left_distance, left_start = distance_and_start(left['drive'])
    right_distance, right_start = distance_and_start(right['drive'])
    left_district, right_district = left['route']['district_type'], right['route']['district_type']
    left_boundary = 30.48 if left_district in ('business', 'residential') else 91.44
    right_boundary = 30.48 if right_district in ('business', 'residential') else 91.44
    if comparison_id in ('business_threshold_below_at', 'business_signal_interruption', 'business_wet_weather'):
        require(left['hashes']['body_history.jsonl'] == right['hashes']['body_history.jsonl'], 'Fixed ego body motion changed')
        require(left['hashes']['route_context.json'] == right['hashes']['route_context.json'], 'Fixed route context changed')
        require(left_district == right_district == 'business', 'Business district context changed')
    if comparison_id == 'business_threshold_below_at':
        require(left['weather'] == right['weather'] and left['weather']['precipitation'] == 0, 'Fixed dry weather changed')
        require(left_distance < 30.48 and math.isclose(right_distance, 30.48, abs_tol=1e-7), 'Below/at distance contrast missing')
        require(left_start > right_start, 'Below/at signal starts are not ordered')
    elif comparison_id == 'business_signal_interruption':
        require(left['weather'] == right['weather'] and left['weather']['precipitation'] == 0, 'Fixed dry weather changed')
        require(left_distance > 30.48 and right_distance < 30.48, 'Interruption distance contrast missing')
        require(left_start < right_start, 'No post-interruption continuous segment observed')
        require(any(not row['right_indicator'] for row in right['drive'][1:-1]), 'No off interval observed')
    elif comparison_id == 'business_wet_weather':
        require(left['hashes']['drive_history.jsonl'] == right['hashes']['drive_history.jsonl'], 'Fixed signal and drive source changed')
        require(left['weather']['precipitation'] == 0 and left['weather']['wetness'] == 0, 'Dry source is not dry')
        require(right['weather']['precipitation'] > 0 and right['weather']['wetness'] > 0, 'Wet source lacks rain readback')
        require(math.isclose(left_distance, right_distance, abs_tol=1e-7), 'Weather pair signal distance changed')
    elif comparison_id == 'district_boundary_100_300':
        require(left_district == 'business' and right_district == 'other', 'District contrast missing')
        require(left['weather'] == right['weather'] and left['weather']['precipitation'] == 0, 'Fixed dry weather changed')
        require(left['route']['approach_road_id'] == right['route']['approach_road_id'], 'Approach road changed')
        require(left['route']['outgoing_road_id'] == right['route']['outgoing_road_id'], 'Right-turn connector changed')
        require(math.isclose(left_distance, 30.48, abs_tol=1e-7) and math.isclose(right_distance, 91.44, abs_tol=1e-7), 'District distance contrast missing')
    else:
        raise ValueError('Unknown comparison: ' + comparison_id)
    return {'format': 'worker-turn-signal-source-comparison', 'comparison_id': comparison_id,
            'source_scope': 'saved synthetic diagnostic original sources',
            'left_source_hashes': left['hashes'], 'right_source_hashes': right['hashes'],
            'left_district': left_district, 'right_district': right_district,
            'left_boundary_m': left_boundary, 'right_boundary_m': right_boundary,
            'left_continuous_signal_distance_m': left_distance,
            'right_continuous_signal_distance_m': right_distance,
            'left_last_signal_start_frame': left_start, 'right_last_signal_start_frame': right_start,
            'left_weather': left['weather'], 'right_weather': right['weather'],
            'software_comparison_passed': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison-id', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison_id, load_sources(args.left), load_sources(args.right)), indent=2))


if __name__ == '__main__':
    main()
