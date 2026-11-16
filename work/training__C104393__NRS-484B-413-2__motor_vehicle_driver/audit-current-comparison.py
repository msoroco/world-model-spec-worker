"""Independently compare exact primary synthetic signal-distance diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FEET = (90, 100, 110, 290, 300, 310)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan = read(HERE / 'case-plan.json')
    manifest = read(HERE / 'draft-execution-manifest.json')
    comparison, = plan['comparisons']
    expected = [f'{HERE.name}__{feet}' for feet in FEET]
    if comparison['case_ids'] != expected:
        raise ValueError('Comparison case membership changed')
    fixed = None
    measurements = {}
    for feet, case_id in zip(FEET, expected):
        entry = next(x for x in manifest['cases'] if x['case_id'] == case_id)
        summary = read(HERE / f'current-v2-{feet}-summary.json')
        if summary['case_id'] != case_id or len(summary['candidate_receipts']) != 4:
            raise ValueError(f'Candidate proof missing: {feet}')
        item = next(x for x in summary['candidate_receipts'] if x['candidate_id'] == 'primary')
        proof_path = HERE / item['receipt']
        if sha(proof_path) != item['sha256']:
            raise ValueError(f'Receipt changed: {feet}')
        proof = read(proof_path)
        if proof['case_id'] != case_id or proof['candidate_id'] != 'primary' or \
           proof['construction_sha256'] != entry['construction_sha256'] or \
           proof['fixture_recipe_sha256'] != sha(HERE / item['recipe']):
            raise ValueError(f'Proof binding changed: {feet}')
        if proof['log_sha256'] != sha(HERE / item['analysis_log']) or \
           proof['negative_log_sha256'] != sha(HERE / item['negative_log']) or \
           'Missing required source: native_samples.jsonl' not in (HERE / item['negative_log']).read_text():
            raise ValueError(f'Positive/negative proof changed: {feet}')
        measured = proof['measurement_examples']['continuous_signal_distance_ft']['value']
        if abs(measured - feet) > 0.5:
            raise ValueError(f'Wrong measured signal distance: {feet}')
        measurements[feet] = measured
        construction = read(HERE / entry['construction'])
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        request = dict(config['native_request'])
        if request.pop('signal_start_ft') != feet:
            raise ValueError(f'Wrong requested signal distance: {feet}')
        request.pop('signal_start_station_m')
        request.pop('case_id')
        request.pop('candidate_id')
        stable = {'request': request, 'cameras': config['cameras'],
                  'actor': config['actor'], 'rate_hz': config['rate_hz'],
                  'duration_s': config['duration_s']}
        if fixed is None:
            fixed = stable
        elif stable != fixed:
            raise ValueError(f'Fixed construction conditions changed: {feet}')
    if not all(measurements[a] < measurements[b] for a, b in zip(FEET, FEET[1:])):
        raise ValueError('Measured order changed')
    return {'format': 'c104393-current-synthetic-comparison-audit', 'passed': True,
            'comparison_id': comparison['comparison_id'], 'case_ids': expected,
            'measured_signal_distance_ft': measurements,
            'fixed_conditions_checked': sorted(fixed), 'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
