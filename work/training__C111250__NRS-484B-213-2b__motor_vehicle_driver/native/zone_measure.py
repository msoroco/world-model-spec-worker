"""Source-bound 100-foot approach and traversal measurement; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FEET_100_M = 30.48


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure(folder):
    folder = Path(folder)
    context_path = require(folder, 'road-context.json')
    poses_path = require(folder, 'vehicle-footprints.jsonl')
    context = json.loads(context_path.read_text())
    if context['approach_axis_xy'] != [1, 0] or context['centerline_y_m'] != 0:
        raise ValueError('This construction is limited to a straight eastbound approach')
    if context['intersection_x_m'] != [0, 20]:
        raise ValueError('Intersection geometry differs from reviewed diagnostic')
    if type(context['one_way_highway']) is not bool:
        raise ValueError('One-way applicability context is unknown')
    rows = [json.loads(line) for line in poses_path.read_text().splitlines() if line.strip()]
    if len(rows) != 600:
        raise ValueError('Expected complete 600-frame 30-second source interval')
    first_active = first_left_active = first_left_approach = first_left_traversal = None
    last_left_before_zone = None
    previous_time = -math.inf
    previous_frame = -1
    for row in rows:
        frame, time = row['native_frame'], row['time_s']
        if type(frame) is not int or frame <= previous_frame or not math.isfinite(time) or time <= previous_time:
            raise ValueError('Original frame/time order invalid')
        if abs(time - frame / 20) > 1e-5:
            raise ValueError('Original frame/time rate join invalid')
        body = row['body_xy_m']
        if len(body) != 4 or any(len(point) != 2 or not all(math.isfinite(v) for v in point) for point in body):
            raise ValueError('Full four-corner vehicle footprint required')
        front = max(point[0] for point in body)
        rear = min(point[0] for point in body)
        left = any(point[1] > 0 for point in body)
        approach = front >= -FEET_100_M and rear < 0
        traversal = front >= 0 and rear <= 20
        active = approach or traversal
        if active and first_active is None:
            first_active = frame
        if left and active and first_left_active is None:
            first_left_active = frame
        if left and approach and first_left_approach is None:
            first_left_approach = frame
        if left and traversal and first_left_traversal is None:
            first_left_traversal = frame
        if left and not active:
            last_left_before_zone = frame
        previous_frame, previous_time = frame, time
    if first_active is None:
        raise ValueError('Capture never reaches 100-foot approach or traversal')
    return {
        'format': 'c111250-original-footprint-zone-measurement-v1',
        'frames': len(rows), 'rate_hz': 20,
        'source_sha256': {'road-context.json': digest(context_path),
                          'vehicle-footprints.jsonl': digest(poses_path)},
        'engineering_distance_m': FEET_100_M,
        'distance_reference': 'first vehicle footprint corner entering straight-line 30.48 m approach',
        'first_active_frame': first_active,
        'last_left_before_zone_frame': last_left_before_zone,
        'first_left_active_frame': first_left_active,
        'first_left_approach_frame': first_left_approach,
        'first_left_traversal_frame': first_left_traversal,
        'one_way_highway': context['one_way_highway'],
        'subsection_2_applicability': 'excluded_by_explicit_one_way_context' if context['one_way_highway'] else 'two_way_context_proposed',
        'measurement_only': True,
        'legal_verdict_claimed': False,
        'limitations': ['Original roadway dedication, access, direction and intersection definition need physical review',
                        'Footprint-corner straight-line distance is an engineering proxy, not an asserted legal measurement rule',
                        'Railroad grade crossing branch needs a separate physically present crossing'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain original measurement; use a fresh output')
    result = measure(args.attempt)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'frames': result['frames'], 'first_left_active_frame': result['first_left_active_frame'],
                      'one_way_highway': result['one_way_highway'], 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
