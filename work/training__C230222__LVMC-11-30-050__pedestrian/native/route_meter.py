"""Measure a complete pedestrian crossing from retained Native source positions.

The returned geometry is diagnostic. A legal reviewer must decide whether a
measured route satisfies either alternative in LVMC 11.30.050.
"""
import hashlib
import json
import math
from pathlib import Path


def distance(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def nearest_on_segment(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 <= 0:
        raise ValueError('Zero-length curb segment')
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2))
    return [a[0] + t * dx, a[1] + t * dy]


def point_in_polygon(p, polygon):
    inside = False
    j = len(polygon) - 1
    for i, a in enumerate(polygon):
        b = polygon[j]
        if ((a[1] > p[1]) != (b[1] > p[1])):
            x = (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]
            if p[0] < x:
                inside = not inside
        j = i
    return inside


def measure(samples, context):
    if len(samples) < 2:
        raise ValueError('Complete crossing trace needs at least two positions')
    frames = [row['native_frame'] for row in samples]
    if len(frames) != len(set(frames)) or any(b <= a for a, b in zip(frames, frames[1:])):
        raise ValueError('Native frame order differs')
    expected = context['expected_frames']
    if len(samples) != expected:
        raise ValueError('Source frame count differs')
    if any(not isinstance(row.get('pedestrian_xy_m'), list) or len(row['pedestrian_xy_m']) != 2 for row in samples):
        raise ValueError('Original pedestrian position missing')
    positions = [row['pedestrian_xy_m'] for row in samples]
    if any(not all(math.isfinite(v) for v in p) for p in positions):
        raise ValueError('Non-finite original position')
    start, end = positions[0], positions[-1]
    origin = context['origin_curb_xy_m']
    target = context['opposite_curb_xy_m']
    if len(origin) != 2 or len(target) != 2:
        raise ValueError('Two curb endpoints required')
    origin_near = nearest_on_segment(start, *origin)
    target_near = nearest_on_segment(end, *target)
    curb_tangent = [origin[1][0] - origin[0][0], origin[1][1] - origin[0][1]]
    displacement = [end[0] - start[0], end[1] - start[1]]
    tangent_length = math.hypot(*curb_tangent)
    displacement_length = math.hypot(*displacement)
    if displacement_length <= 0:
        raise ValueError('No observed route displacement')
    tangent_dot = abs(sum(a * b for a, b in zip(curb_tangent, displacement))) / (tangent_length * displacement_length)
    angle_from_right_angle_deg = math.degrees(math.asin(min(1.0, tangent_dot)))
    route_length = sum(distance(a, b) for a, b in zip(positions, positions[1:]))
    shortest_endpoint = nearest_on_segment(start, *target)
    shortest_length = distance(start, shortest_endpoint)
    polygons = context.get('crosswalk_polygons_xy_m', [])
    crosswalk_sample_count = sum(any(point_in_polygon(p, polygon) for polygon in polygons) for p in positions)
    return {
        'format': 'worker-route-geometry-measurement-v1',
        'law_id': 'LVMC-11-30-050',
        'source_kind': context['source_kind'],
        'frames': len(samples),
        'first_native_frame': frames[0],
        'last_native_frame': frames[-1],
        'entry_xy_m': start,
        'exit_xy_m': end,
        'entry_distance_to_origin_curb_m': distance(start, origin_near),
        'exit_distance_to_opposite_curb_m': distance(end, target_near),
        'route_length_m': route_length,
        'shortest_to_opposite_curb_m': shortest_length,
        'route_excess_length_m': route_length - shortest_length,
        'right_angle_deviation_deg': angle_from_right_angle_deg,
        'crosswalk_sample_count': crosswalk_sample_count,
        'alternatives': ['right_angle_to_curb', 'shortest_route_to_opposite_curb'],
    }


def measure_files(samples_path, context_path, output_path):
    samples_path, context_path, output_path = map(Path, (samples_path, context_path, output_path))
    samples = [json.loads(line) for line in samples_path.read_text().splitlines() if line]
    context = json.loads(context_path.read_text())
    if context.get('source_kind') not in ('native_observation', 'synthetic_cpu_fixture'):
        raise ValueError('Unknown source kind')
    report = measure(samples, context)
    report['source_samples_sha256'] = hashlib.sha256(samples_path.read_bytes()).hexdigest()
    report['source_context_sha256'] = hashlib.sha256(context_path.read_bytes()).hexdigest()
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 4:
        raise SystemExit('usage: route_meter.py SOURCE_SAMPLES CONTEXT OUTPUT')
    print(json.dumps(measure_files(*sys.argv[1:])))
