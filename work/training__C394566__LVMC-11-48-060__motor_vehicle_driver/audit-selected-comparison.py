"""Independent source-bound purpose comparison over the two selected diagnostics."""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXED = ('entry_truck_route_id', 'intervening_street_id', 'exit_truck_route_id',
         'vehicle_is_truck', 'truck_blueprint_source', 'truck_route_designation_source',
         'nontruck_street_designation_source', 'route_connectivity_source')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(probe, short):
    path = HERE / ('diagnostic-' + probe + '.json')
    recipe = read(HERE / ('fixture-recipe-' + probe + '.json'))
    if recipe['generator']['sha256'] != sha(path):
        raise ValueError('Comparison diagnostic source changed')
    files = read(path)['files']
    compat = read(HERE / f'compat-{short}-pr/receipt.json')
    saved = read(HERE / f'saved-{short}-processing.json')
    for name in ('route_context.json', 'native_route_trace.jsonl', 'video_frames.jsonl'):
        if compat['fixture_manifest'][name] != hashlib.sha256(files[name].encode()).hexdigest():
            raise ValueError('Comparison selected source differs from compatibility')
        if saved['original_source_hashes'][name] != compat['fixture_manifest'][name]:
            raise ValueError('Comparison saved original source differs')
    if not saved['recorded_only'] or not saved['originals_preserved'] or saved['missing_evidence']:
        raise ValueError('Comparison lacks successful saved-only proof')
    return json.loads(files['route_context.json']), [json.loads(x) for x in files['native_route_trace.jsonl'].splitlines()]


def samples(rows, count=21):
    points = [(row['ego_x_m'], row['ego_y_m']) for row in rows]
    cumulative = [0.0]
    for a, b in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.dist(a, b))
    if cumulative[-1] <= 0:
        raise ValueError('Comparison route has no progress')
    result = []
    for j in range(count):
        target = cumulative[-1] * j / (count - 1)
        index = next((i for i, distance in enumerate(cumulative) if distance >= target), len(rows) - 1)
        result.append(points[index])
    return result, cumulative[-1]


def audit(reject_comparison_drift=False):
    a, first = source('probe_01', 'p01')
    b, second = source('probe_02', 'p02')
    if reject_comparison_drift:
        b['route_connectivity_source'] = 'changed diagnostic route'
    if any(a.get(key) != b.get(key) for key in FIXED):
        raise ValueError('Comparison fixed route or truck context changed')
    if a['enroute_purpose'] != 'none' or b['enroute_purpose'] not in ('pickup', 'delivery', 'essential'):
        raise ValueError('Comparison lacks reviewed enroute purpose difference')
    if len(first) != 600 or len(second) != 600:
        raise ValueError('Comparison lacks full original route sources')
    route_a = [row['road_id'] for row in first]
    route_b = [row['road_id'] for row in second]
    expected = [a['entry_truck_route_id'], a['intervening_street_id'], a['exit_truck_route_id']]
    for route in (route_a, route_b):
        sequence = []
        for road in route:
            if not sequence or sequence[-1] != road:
                sequence.append(road)
        if sequence != expected:
            raise ValueError('Comparison route sequence differs')
    positions_a, length_a = samples(first)
    positions_b, length_b = samples(second)
    spatial = max(math.dist(x, y) for x, y in zip(positions_a, positions_b))
    if spatial > 5.0 or abs(length_a - length_b) > 5.0:
        raise ValueError('Comparison changed original route geometry')
    stops = [i for i, row in enumerate(second) if row['service_stop_active']]
    if len(stops) != 100 or stops != list(range(stops[0], stops[-1] + 1)):
        raise ValueError('Comparison lacks original continuous service stop')
    return {'passed': True, 'case_ids': [a['case_id'], b['case_id']],
            'fixed_route_ids': expected, 'purpose_change': [a['enroute_purpose'], b['enroute_purpose']],
            'max_spatial_difference_m': spatial, 'path_length_difference_m': abs(length_a - length_b),
            'service_stop_frames': len(stops), 'source_bound': True,
            'scope': 'synthetic source and saved-receipt comparison; physical and legal review pending'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reject-comparison-drift', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.reject_comparison_drift), indent=2))


if __name__ == '__main__':
    main()
