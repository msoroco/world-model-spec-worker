"""Independent source-bound audit of both synthetic signal-distance comparisons."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIX_GROUPS = [('below_100_ft', 'at_100_ft', 'above_100_ft'),
                 ('below_300_ft', 'at_300_ft', 'above_300_ft')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measured_distance(samples):
    assert len(samples) == 800
    changes = [i for i, row in enumerate(samples) if row['course_change']]
    assert len(changes) == 1
    end = changes[0]
    assert samples[end]['signal'] == 'left'
    begin = end
    while begin > 0 and samples[begin - 1]['signal'] == 'left':
        begin -= 1
    assert begin > 0 and samples[begin - 1]['signal'] == 'off'
    assert all(row['signal'] == 'left' for row in samples[begin:end + 1])
    distance_m = sum(math.dist(samples[i - 1]['native_center_xy_m'],
                               samples[i]['native_center_xy_m'])
                     for i in range(begin + 1, end + 1))
    return begin, end, distance_m / .3048


def fixed_profile(samples):
    return [tuple((row['native_frame'], row['time_s'], tuple(row['native_center_xy_m']),
                   tuple(row['native_forward_xy']), row['speed_mps'], row['heading_deg'],
                   row['area'], row['weather'], row['course_change'], row['route_error_m']))
            for row in samples]


def audit_group(suffixes, comparison_id):
    proofs = []
    native_rows = []
    for suffix in suffixes:
        path = HERE / ('current-v2-' + suffix + '-primary-proof.json')
        proof = json.loads(path.read_text())
        native = HERE / 'current-v2-case-sources' / suffix / 'native_samples.jsonl'
        assert proof['case_id'].endswith('__' + suffix)
        assert proof['compatibility']['passed'] and proof['recorded_only']['passed']
        assert proof['native_samples_sha256'] == sha(native)
        assert proof['synthetic_cpu_only'] and not proof['physical_acceptance_claimed']
        assert not proof['legal_verdict_claimed']
        assert proof['compatibility']['negative_removed'] == 'native_samples.jsonl'
        samples = rows(native)
        assert all(row['area'] == samples[0]['area'] and row['weather'] == 'clear' for row in samples)
        begin, end, value = measured_distance(samples)
        assert abs(value - proof['compatibility']['continuous_signal_distance_ft']) < 1e-8
        proofs.append({'case_id': proof['case_id'], 'proof_sha256': sha(path),
                       'native_samples_sha256': sha(native), 'signal_onset_index': begin,
                       'course_change_index': end, 'distance_ft': value})
        native_rows.append(samples)
    assert fixed_profile(native_rows[0]) == fixed_profile(native_rows[1]) == fixed_profile(native_rows[2])
    assert proofs[0]['signal_onset_index'] > proofs[1]['signal_onset_index'] > proofs[2]['signal_onset_index']
    assert proofs[0]['distance_ft'] < proofs[1]['distance_ft'] < proofs[2]['distance_ft']
    assert all(item['course_change_index'] == proofs[0]['course_change_index'] for item in proofs)
    # Source mutation checks exercise the fixed-profile and measured interval audits.
    wrong_area = [dict(row) for row in native_rows[1]]
    wrong_area[0]['area'] = ('other' if native_rows[0][0]['area'] != 'other'
                             else 'business_or_residential')
    assert fixed_profile(wrong_area) != fixed_profile(native_rows[0])
    wrong_signal = [dict(row) for row in native_rows[1]]
    wrong_signal[proofs[1]['signal_onset_index'] + 5]['signal'] = 'off'
    _, _, wrong_distance = measured_distance(wrong_signal)
    assert abs(wrong_distance - proofs[1]['distance_ft']) > 1
    return {'comparison_id': comparison_id, 'passed': True, 'cases': proofs,
            'fixed_checks': ['cell', 'actor', 'area', 'weather', 'route', 'speed',
                             'course_change', 'capture_rate', 'source_proof'],
            'negative_mutations_rejected': ['area', 'interior_signal_gap']}


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparisons = {entry['comparison_id']: entry for entry in plan['comparisons']}
    results = []
    for group in SUFFIX_GROUPS:
        ident = HERE.name + ('__comparison_100ft' if group[0] == 'below_100_ft'
                             else '__comparison_300ft')
        expected = [HERE.name + '__' + suffix for suffix in group]
        assert comparisons[ident]['case_ids'] == expected
        results.append(audit_group(group, ident))
    output = HERE / 'current-v2-boundary-comparison-audit.json'
    output.write_text(json.dumps({'format': 'c329610-current-v2-comparison-audit-v1',
                                  'passed': True, 'synthetic_cpu_only': True,
                                  'comparisons': results}, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'comparison_count': len(results),
                      'audit_sha256': sha(output)}, sort_keys=True))


if __name__ == '__main__':
    main()
