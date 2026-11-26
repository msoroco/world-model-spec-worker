"""Audit officer candidate presence contrast, leaving authority unresolved."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_pair(vehicle_a, vehicle_b, officer_a, officer_b, maps_equal=True):
    if not all(len(group) == 600 for group in (vehicle_a, vehicle_b, officer_a, officer_b)):
        raise ValueError('Missing fixed comparison frames')
    if not maps_equal:
        raise ValueError('Uncontrolled map difference')
    actor_ids = set()
    for index in range(600):
        a, b = vehicle_a[index], vehicle_b[index]
        if a != b:
            raise ValueError('Uncontrolled subject motion or source difference')
        x, y = officer_a[index], officer_b[index]
        for officer, vehicle in ((x, a), (y, b)):
            if (officer.get('frame') != index or
                    officer.get('native_frame') != vehicle['native_frame'] or
                    abs(float(officer['time_s']) - float(vehicle['time_s'])) > 1e-4):
                raise ValueError('Officer candidate frame/time differs')
            if officer.get('identity_verified') is not False or officer.get('direction_observed') is not None:
                raise ValueError('Diagnostic officer source preclaims authority')
        if x.get('actor_id') is not None or y.get('actor_id') is None:
            raise ValueError('Officer candidate presence contrast differs')
        if y['actor_id'] == b['actor_id'] or not str(y.get('blueprint_id', '')).startswith('walker.pedestrian.'):
            raise ValueError('Officer candidate identity aliases subject or wrong actor')
        actor_ids.add(y['actor_id'])
    if len(actor_ids) != 1:
        raise ValueError('Officer candidate identity changes during comparison')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    pair = next(row for row in plan['comparisons'] if row['comparison_id'].endswith('__officer_direction_comparison'))
    roots = [HERE / 'diagnostic-source' / ('officer_direction_' + state)
             for state in ('absent', 'present')]
    vehicle = HERE / 'diagnostic-source/probe_2/vehicle-trace.jsonl'
    vehicles = [rows(vehicle), rows(vehicle)]
    officers = [rows(root / 'officer-trace.jsonl') for root in roots]
    map_path = HERE / 'diagnostic-source/probe_2/map-packet.json'
    check_pair(*vehicles, *officers, maps_equal=True)
    rejected = []
    for mutation in ('short', 'subject_motion', 'no_officer_contrast', 'actor_alias',
                     'identity_change', 'authority_preclaim', 'map'):
        va, vb = [list(map(dict, group)) for group in vehicles]
        oa, ob = [list(map(dict, group)) for group in officers]
        same_map = True
        if mutation == 'short':
            ob.pop()
        elif mutation == 'subject_motion':
            vb[240]['speed_mps'] += 1
        elif mutation == 'no_officer_contrast':
            ob = [dict(row) for row in oa]
        elif mutation == 'actor_alias':
            ob[240]['actor_id'] = vb[240]['actor_id']
        elif mutation == 'identity_change':
            ob[240]['actor_id'] = 999
        elif mutation == 'authority_preclaim':
            ob[240]['identity_verified'] = True
        else:
            same_map = False
        try:
            check_pair(va, vb, oa, ob, maps_equal=same_map)
        except ValueError:
            rejected.append(mutation)
        else:
            raise AssertionError('Uncontrolled officer comparison accepted: ' + mutation)
    spec = {'format': 'c229977-officer-comparison-v1',
            'comparison_id': pair['comparison_id'], 'case_ids': pair['case_ids'],
            'changed_request_keys': ['officer_candidate_present'],
            'fixed_subject_trace_sha256': sha(vehicle), 'fixed_map_sha256': sha(map_path),
            'diagnostic_officer_trace_sha256': [sha(root / 'officer-trace.jsonl') for root in roots],
            'diagnostic_authority_context_sha256': [sha(root / 'authority-context.json') for root in roots],
            'negative_mutations_rejected': rejected, 'source_originality': 'diagnostic_only',
            'officer_identity_direction_and_compliance_independently_verified': False,
            'original_native_outcome_reviewed': False, 'legal_conclusion': None}
    target = HERE / 'officer-comparison-audit-spec.json'
    target.write_text(json.dumps(spec, indent=2) + '\n')
    print(json.dumps({'comparison_id': pair['comparison_id'], 'spec_sha256': sha(target)}))


if __name__ == '__main__':
    main()
