"""Independent original-source comparison of through trip and enroute service trip."""
import argparse
import json
import math
from pathlib import Path

from measure_through_route import AID, measure, rows
from measure_purpose_route import measure_purpose


FIXED_CONTEXT = ('entry_truck_route_id', 'intervening_street_id', 'exit_truck_route_id',
                 'vehicle_is_truck', 'truck_blueprint_source', 'truck_route_designation_source',
                 'nontruck_street_designation_source', 'route_connectivity_source')


def spatial_samples(trace, count=21):
    points = [(row['ego_x_m'], row['ego_y_m']) for row in trace]
    cumulative = [0.0]
    for a, b in zip(points, points[1:]):
        cumulative.append(cumulative[-1]+math.dist(a, b))
    if cumulative[-1] <= 0:
        raise ValueError('Original route has no spatial progress')
    result = []
    for j in range(count):
        target = cumulative[-1]*j/(count-1)
        index = next((i for i, distance in enumerate(cumulative) if distance >= target), len(cumulative)-1)
        result.append(points[index])
    return result


def audit(no_purpose_root, purpose_root):
    no_purpose_root, purpose_root = Path(no_purpose_root), Path(purpose_root)
    first = measure(no_purpose_root)
    second = measure_purpose(purpose_root)
    if first['case_id'] != AID+'__probe_01' or second['case_id'] != AID+'__probe_02':
        raise ValueError('Comparison exact case identities differ')
    a = json.loads((no_purpose_root/'route_context.json').read_text())
    b = json.loads((purpose_root/'route_context.json').read_text())
    if any(a.get(key) != b.get(key) for key in FIXED_CONTEXT):
        raise ValueError('Comparison changed route designation or truck context')
    if not first['vehicle_is_truck_reviewed'] or not second['vehicle_is_truck_reviewed']:
        raise ValueError('Comparison lacks reviewed truck class')
    if (not first['complete_truck_to_truck_passage'] or
            first['observed_road_sequence'] != second['observed_road_sequence']):
        raise ValueError('Comparison route sequence differs')
    if first['enroute_purpose_reviewed'] != 'none' or second['enroute_purpose_reviewed'] not in ('pickup', 'delivery', 'essential'):
        raise ValueError('Comparison did not vary reviewed enroute purpose')
    ta = rows(no_purpose_root/'native_route_trace.jsonl')
    tb = rows(purpose_root/'native_route_trace.jsonl')
    max_spatial_difference = max(math.dist(x, y) for x, y in zip(spatial_samples(ta), spatial_samples(tb)))
    if max_spatial_difference > 5.0:
        raise ValueError('Comparison changed original route geometry')
    if abs(first['observed_path_length_m']-second['observed_path_length_m']) > 5.0:
        raise ValueError('Comparison changed route length')
    return {'format': 'truck-through-route-comparison-audit',
            'assignment_id': AID, 'case_ids': [first['case_id'], second['case_id']],
            'source_hashes': {'probe_01': first['sources'], 'probe_02': second['sources']},
            'fixed_route_ids': first['reviewed_route_ids'],
            'max_spatial_difference_m': max_spatial_difference,
            'purpose_change': ['none', second['enroute_purpose_reviewed']],
            'service_stop_frames': second['reviewed_service_stop_frames'],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('no_purpose_source', type=Path)
    parser.add_argument('purpose_source', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    args.output_json.write_text(json.dumps(audit(args.no_purpose_source, args.purpose_source), indent=2)+'\n')
