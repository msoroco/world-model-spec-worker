"""Audit traffic-actor contrast while retaining legal necessity as unknown."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_pair(vehicle_a, vehicle_b, traffic_a, traffic_b, maps_equal=True):
    if not all(len(group) == 600 for group in (vehicle_a, vehicle_b, traffic_a, traffic_b)):
        raise ValueError('Missing fixed comparison frames')
    if not maps_equal:
        raise ValueError('Uncontrolled map difference')
    for index in range(600):
        a, b = vehicle_a[index], vehicle_b[index]
        if a != b:
            raise ValueError('Uncontrolled subject motion or source difference')
        if traffic_a[index].get('frame') != index or traffic_b[index].get('frame') != index:
            raise ValueError('Traffic frame differs')
        if traffic_a[index].get('native_frame') != a['native_frame'] or traffic_b[index].get('native_frame') != b['native_frame']:
            raise ValueError('Traffic native frame differs')
        if abs(float(traffic_a[index]['time_s']) - float(a['time_s'])) > 1e-4 or abs(float(traffic_b[index]['time_s']) - float(b['time_s'])) > 1e-4:
            raise ValueError('Traffic time differs')
        if 'actor_id' in traffic_a[index] or 'actor_id' not in traffic_b[index]:
            raise ValueError('Traffic actor contrast differs')
        if traffic_b[index]['actor_id'] == b['actor_id']:
            raise ValueError('Traffic actor identity aliases subject')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    pair = next(row for row in plan['comparisons'] if row['comparison_id'].endswith('__traffic_conflict_comparison'))
    roots = [HERE / 'diagnostic-source' / ('traffic_conflict_' + state) for state in ('absent', 'present')]
    vehicle = HERE / 'diagnostic-source/probe_2/vehicle-trace.jsonl'
    vehicles = [rows(vehicle), rows(vehicle)]
    traffic = [rows(root / 'traffic-trace.jsonl') for root in roots]
    maps = [HERE / 'diagnostic-source/probe_2/map-packet.json'] * 2
    check_pair(*vehicles, *traffic, maps_equal=sha(maps[0]) == sha(maps[1]))
    rejected = []
    for mutation in ('short', 'subject_motion', 'no_traffic_contrast', 'actor_alias', 'map'):
        va, vb = [list(map(dict, group)) for group in vehicles]
        ta, tb = [list(map(dict, group)) for group in traffic]
        same_map = True
        if mutation == 'short':
            tb.pop()
        elif mutation == 'subject_motion':
            vb[240]['speed_mps'] += 1
        elif mutation == 'no_traffic_contrast':
            tb = [dict(row) for row in ta]
        elif mutation == 'actor_alias':
            tb[240]['actor_id'] = vb[240]['actor_id']
        else:
            same_map = False
        try:
            check_pair(va, vb, ta, tb, maps_equal=same_map)
        except ValueError:
            rejected.append(mutation)
        else:
            raise AssertionError('Uncontrolled comparison accepted: ' + mutation)
    spec = {'format': 'c229977-traffic-comparison-v1',
            'comparison_id': pair['comparison_id'], 'case_ids': pair['case_ids'],
            'changed_request_keys': ['other_traffic_actor_present'],
            'fixed_subject_trace_sha256': sha(vehicle), 'fixed_map_sha256': sha(maps[0]),
            'diagnostic_traffic_trace_sha256': [sha(root / 'traffic-trace.jsonl') for root in roots],
            'diagnostic_authority_context_sha256': [sha(root / 'authority-context.json') for root in roots],
            'negative_mutations_rejected': rejected,
            'source_originality': 'diagnostic_only',
            'necessity_independently_verified': False,
            'original_native_outcome_reviewed': False,
            'legal_conclusion': None}
    target = HERE / 'traffic-comparison-audit-spec.json'
    target.write_text(json.dumps(spec, indent=2) + '\n')
    print(json.dumps({'comparison_id': pair['comparison_id'], 'spec_sha256': sha(target)}))


if __name__ == '__main__':
    main()
