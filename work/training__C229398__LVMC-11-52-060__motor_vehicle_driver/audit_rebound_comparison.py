"""Audit the manifest-bound 14/15/16-foot synthetic comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = ('below_15_ft', 'at_15_ft', 'above_15_ft')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    manifest_sha = sha(manifest_path)
    cases = {case['case_id'].rsplit('__', 1)[-1]: case for case in manifest['cases']}
    assert set(cases) == set(GROUPS)
    plan = read(HERE / 'case-plan.json')
    comparison = plan['comparisons'][0]
    assert comparison['deliberate_differences'] == ['maximum_projection_perpendicular_to_curb']
    source_path = HERE / 'saved-source-proof.json'
    source = read(source_path)
    assert source['passed'] and source['source_kind'] == 'synthetic_native_sample'
    source_cases = {case['case_id']: case for case in source['cases']}
    fixed = []
    rows = []
    for group in GROUPS:
        entry = cases[group]
        case_id = entry['case_id']
        source_case = source_cases[case_id]
        construction = HERE / entry['construction']
        assert sha(construction) == entry['construction_sha256'] == source_case['construction_sha256']
        config = read(construction)
        config = json.loads(next(item['content'] for item in config['files']
                                 if item['path'] == 'config.json'))
        assert config['duration_s'] == 30 and config['rate_hz'] == 20
        target = config['target_projection_ft']
        assert target == source_case['requested_ft']
        assert abs(source_case['measured_ft'] - target) < 0.01
        raw = HERE / 'diagnostic-fixture' / group / 'sources/native-raw-actors.jsonl'
        assert sha(raw) == source_case['raw_source_sha256']
        prefix = 'rebound-chain-' + group + '-primary'
        selection_path = HERE / (prefix + '-offline-selection.json')
        positive_path = HERE / (prefix + '-compatibility.log')
        negative_path = HERE / (prefix + '-negative-analysis.log')
        saved_path = HERE / (prefix + '-saved.log')
        chain_path = HERE / (prefix + '-proof.json')
        selection, positive, saved, chain = map(read,
            (selection_path, positive_path, saved_path, chain_path))
        assert selection['manifest_sha256'] == manifest_sha
        assert selection['construction_sha256'] == entry['construction_sha256']
        assert positive['case_id'] == saved['case_id'] == case_id
        assert positive['passed'] and saved['passed'] and saved['recorded_only']
        assert positive['construction_sha256'] == entry['construction_sha256']
        assert positive['negative_error_contains'] in negative_path.read_text()
        assert positive['negative_log_sha256'] == sha(negative_path)
        assert saved['native_revision']['construction_sha256'] == entry['construction_sha256']
        assert chain['selected_manifest_sha256'] == manifest_sha and chain['cpu_chain_passed']
        measurement = positive['measurement_examples']['text_0_projection']['value']
        assert abs(measurement - source_case['measured_ft']) < 0.01
        common = dict(config)
        for key in ('case', 'case_id', 'case_suffix', 'selected_case_id',
                    'target_projection_ft'):
            common.pop(key, None)
        fixed.append(common)
        rows.append({'case_id': case_id, 'requested_ft': target,
                     'measured_ft': measurement, 'frames': source_case['channel_frames'],
                     'construction_sha256': entry['construction_sha256'],
                     'raw_source_sha256': sha(raw), 'chain_proof_sha256': sha(chain_path),
                     'compatibility_sha256': sha(positive_path),
                     'saved_sha256': sha(saved_path)})
    assert fixed[0] == fixed[1] == fixed[2]
    assert [row['requested_ft'] for row in rows] == [14, 15, 16]
    assert [row['frames'] for row in rows] == [600] * 3
    assert rows[0]['measured_ft'] < rows[1]['measured_ft'] < rows[2]['measured_ft']
    receipt = {'format': 'c229398-manifestbound-synthetic-comparison-audit-v1',
               'passed': True, 'diagnostic_only': True,
               'manifest_sha256': manifest_sha, 'source_proof_sha256': sha(source_path),
               'comparison_id': comparison['comparison_id'],
               'fixed_config_sha256': hashlib.sha256(json.dumps(fixed[0], sort_keys=True).encode()).hexdigest(),
               'cases': rows, 'original_native_observed': False,
               'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output = HERE / 'rebound-comparison-audit.json'
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'cases': len(rows), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
