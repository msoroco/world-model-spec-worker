"""Audit controlled three-case request and source-shaped geometric contrast."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('0.45', '0.55', '1.00')
PREFIX = {'0.45': '045', '0.55': '055', '1.00': '100'}


def audit():
    requests = {}
    measurements = {}
    for case in CASES:
        bundle = json.loads((HERE / 'bundles' / case / 'construction.json').read_text())
        request = next(item['content'] for item in bundle['files'] if item['path'] == 'request.jsonl')
        requests[case] = [json.loads(line) for line in request.splitlines()]
        receipt = json.loads((HERE / 'proofs' / f'{PREFIX[case]}_primary_compatibility.json').read_text())
        measurements[case] = receipt['measurement_examples']['opposite_direction_paved_half_measurement']['value']
    for i in range(600):
        rows = [requests[case][i] for case in CASES]
        if any(row['frame'] != i or row['time_s'] != i / 20 for row in rows):
            raise ValueError('Frame/time comparison differs')
        for row in rows[1:]:
            changed = {key for key in rows[0] if rows[0][key] != row[key]}
            if changed != {'ego_center_xyz_m', 'requested_ego_right_half_body_fraction'}:
                raise ValueError('Comparison changes an uncontrolled request')
            if row['ego_center_xyz_m'][0] != rows[0]['ego_center_xyz_m'][0] or row['ego_center_xyz_m'][2] != rows[0]['ego_center_xyz_m'][2]:
                raise ValueError('Longitudinal or vertical ego motion differs')
    observed = []
    for case in CASES:
        m = measurements[case]
        right = m['right_passing_condition']['observed']
        half = m['one_half_paved_portion_condition']
        if m['source_kind'] != 'synthetic_original_shape' or not m['diagnostic_fixture'] or m['legal_compliance'] != 'unassessed' or right is not True:
            raise ValueError('Comparison source or right passing differs')
        if abs(m['ego_right_paved_half_footprint_fraction_min'] - float(case)) > 1e-6:
            raise ValueError('Requested body fraction not observed')
        observed.append((case, half['minimum_fraction_available_to_oncoming'], half['minimum_fraction_available_to_ego']))
    if not (observed[0][1] < observed[1][1] < 0.5 and observed[2][1] == 0.5 and all(x[2] >= 0.5 for x in observed)):
        raise ValueError('Geometric half-width reference contrast missing')
    return {'format': 'c111294-three-case-cpu-comparison', 'frames': 600,
            'case_ids': [HERE.parent.name + '__' + case for case in CASES],
            'requested_fraction': [float(case) for case in CASES],
            'measured_available_fraction_to_oncoming': [x[1] for x in observed],
            'measured_available_fraction_to_ego': [x[2] for x in observed],
            'right_passing_observed_each': True, 'source_kind': 'synthetic_original_shape',
            'legal_compliance': 'unassessed', 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
