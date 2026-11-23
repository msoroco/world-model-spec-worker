"""Check the selected projection comparison for every exact fallback choice.

The receipt covers synthetic CPU sources only. Native observations and legal
conclusions remain for independent local review after capture.
"""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GROUPS = ('below_15_ft', 'at_15_ft', 'above_15_ft')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
CASE_FIELDS = {'case', 'case_id', 'case_suffix', 'selected_case_id', 'candidate_id',
               'target_projection_ft'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def configuration(path):
    bundle = read(path)
    return json.loads(next(item['content'] for item in bundle['files']
                           if item['path'] == 'config.json'))


def fixed_signature(config):
    return {key: value for key, value in config.items() if key not in CASE_FIELDS}


def check_row(entry, candidate, group, manifest_sha):
    case_id = entry['case_id']
    selected = entry if candidate == 'primary' else next(
        item for item in entry['candidates'] if item['id'] == candidate)
    construction_path = HERE / selected['construction']
    if sha(construction_path) != selected['construction_sha256']:
        raise ValueError('Selected construction hash changed')
    config = configuration(construction_path)
    prefix = f'finalbound-chain-{group}-{candidate}'
    paths = {name: HERE / (prefix + suffix) for name, suffix in {
        'selection': '-offline-selection.json',
        'positive': '-compatibility.log',
        'negative': '-negative-analysis.log',
        'saved': '-saved.log',
        'chain': '-proof.json',
    }.items()}
    selection, positive, saved, chain = (read(paths[key]) for key in
                                         ('selection', 'positive', 'saved', 'chain'))
    if (selection['manifest_sha256'] != manifest_sha
            or selection['construction_sha256'] != selected['construction_sha256']
            or chain['selected_manifest_sha256'] != manifest_sha
            or chain['case_id'] != case_id or chain['candidate'] != candidate
            or not chain['cpu_chain_passed']):
        raise ValueError('Selected manifest or candidate chain differs')
    for filename, expected in chain['receipts'].items():
        if sha(HERE / filename) != expected:
            raise ValueError('Selected chain receipt changed')
    if (positive['case_id'] != case_id or positive['candidate_id'] != candidate
            or positive['construction_sha256'] != selected['construction_sha256']
            or not positive['passed']
            or positive['negative_log_sha256'] != sha(paths['negative'])
            or positive['negative_error_contains'] not in paths['negative'].read_text()
            or saved['case_id'] != case_id or saved['candidate_id'] != candidate
            or saved['native_revision']['construction_sha256'] != selected['construction_sha256']
            or not saved['passed'] or not saved['recorded_only']
            or not saved['originals_preserved']):
        raise ValueError('Compatibility or recorded-only processing differs')
    source_hashes = positive['measurement_examples']['text_0_projection']['sources']
    raw = HERE / 'diagnostic-fixture' / group / 'sources/native-raw-actors.jsonl'
    curb = HERE / 'diagnostic-fixture' / group / 'sources/reviewed-curb.json'
    if (source_hashes['native-raw-actors.jsonl'] != sha(raw)
            or source_hashes['reviewed-curb.json'] != sha(curb)
            or saved['original_source_hashes']['native-raw-actors.jsonl'] != sha(raw)
            or saved['original_source_hashes']['reviewed-curb.json'] != sha(curb)):
        raise ValueError('Measurement differs from retained raw source')
    measured = positive['measurement_examples']['text_0_projection']['value']
    if abs(measured - config['target_projection_ft']) >= 0.01:
        raise ValueError('Measured projection differs from requested probe')
    if config['duration_s'] != 30 or config['rate_hz'] != 20 or len(config['cameras']) != 4:
        raise ValueError('Capture profile differs')
    return {'case_id': case_id, 'candidate': candidate,
            'requested_ft': config['target_projection_ft'], 'measured_ft': measured,
            'construction_sha256': selected['construction_sha256'],
            'chain_proof_sha256': sha(paths['chain']), 'raw_source_sha256': sha(raw),
            'curb_source_sha256': sha(curb), 'fixed': fixed_signature(config)}


def check_comparison(rows):
    by_candidate = {candidate: [row for row in rows if row['candidate'] == candidate]
                    for candidate in CANDIDATES}
    for candidate, group_rows in by_candidate.items():
        if (len(group_rows) != 3
                or [row['requested_ft'] for row in group_rows] != [14, 15, 16]
                or not group_rows[0]['measured_ft'] < group_rows[1]['measured_ft'] < group_rows[2]['measured_ft']
                or group_rows[0]['fixed'] != group_rows[1]['fixed']
                or group_rows[0]['fixed'] != group_rows[2]['fixed']):
            raise ValueError('Comparison changes a fixed condition or loses projection order: ' + candidate)
    primary_fixed = by_candidate['primary'][0]['fixed']
    for candidate, changed in (('fallback1', 'load_height_m'),
                               ('fallback2', 'trailer_rear_m'),
                               ('fallback3', 'camera_distance_m')):
        current = by_candidate[candidate][0]['fixed']
        differences = {key for key in primary_fixed if primary_fixed[key] != current[key]}
        if differences != {changed}:
            raise ValueError('Fallback changes an undeclared knob: ' + candidate)
    return by_candidate


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest, manifest_sha = read(manifest_path), sha(manifest_path)
    cases = {entry['case_id'].rsplit('__', 1)[-1]: entry for entry in manifest['cases']}
    if set(cases) != set(GROUPS):
        raise ValueError('Selected comparison case set differs')
    plan = read(HERE / 'case-plan.json')
    comparison = plan['comparisons'][0]
    if (set(comparison['case_ids']) != {entry['case_id'] for entry in cases.values()}
            or comparison['deliberate_differences'] != ['maximum_projection_perpendicular_to_curb']):
        raise ValueError('Selected comparison plan differs')
    rows = [check_row(cases[group], candidate, group, manifest_sha)
            for candidate in CANDIDATES for group in GROUPS]
    by_candidate = check_comparison(rows)
    negatives = 0
    for candidate in CANDIDATES:
        corrupted = copy.deepcopy(rows)
        next(row for row in corrupted if row['candidate'] == candidate
             and row['requested_ft'] == 15)['fixed']['weather'] = 'corrupted-weather'
        try:
            check_comparison(corrupted)
        except ValueError as error:
            if 'fixed condition' not in str(error):
                raise
            negatives += 1
        else:
            raise ValueError('Altered fixed weather was accepted')
    corrupted = copy.deepcopy(rows)
    next(row for row in corrupted if row['candidate'] == 'fallback2'
         and row['requested_ft'] == 14)['fixed']['load_height_m'] = 1.2
    try:
        check_comparison(corrupted)
    except ValueError as error:
        if 'fixed condition' not in str(error):
            raise
        negatives += 1
    else:
        raise ValueError('Undeclared fallback knob was accepted')
    receipt = {'format': 'c229398-finalbound-candidate-comparison-cpu-v1',
               'passed': True, 'diagnostic_only': True,
               'manifest_sha256': manifest_sha,
               'comparison_id': comparison['comparison_id'],
               'candidate_groups': {candidate: {
                   'fixed_config_sha256': canonical_hash(group_rows[0]['fixed']),
                   'rows': [{key: value for key, value in row.items() if key != 'fixed'}
                            for row in group_rows]}
                   for candidate, group_rows in by_candidate.items()},
               'selected_chains': len(rows), 'negative_mutations_rejected': negatives,
               'source_footprint_audit_sha256': sha(HERE / 'finalbound-footprint-source-join.json'),
               'original_native_observed': False, 'physical_acceptance_claimed': False,
               'legal_verdict_claimed': False}
    output = HERE / 'finalbound-candidate-comparison-cpu.json'
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'selected_chains': len(rows),
                      'negative_mutations_rejected': negatives, 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
