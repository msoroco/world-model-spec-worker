"""Independently check the synthetic 14/15/16-foot projection comparison."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
MANIFEST = PACKAGE / 'draft-primary-manifest.json'
SUFFIXES = ('below_15_ft', 'at_15_ft', 'above_15_ft')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    source_proof_path = PACKAGE / 'saved-source-proof.json'
    source_proof = json.loads(source_proof_path.read_text())
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    assert source_proof['passed'] and source_proof['source_kind'] == 'synthetic_native_sample'
    assert len(manifest['cases']) == len(source_proof['cases']) == len(SUFFIXES) == 3
    comparison = plan['comparisons'][0]
    assert comparison['deliberate_differences'] == ['maximum_projection_perpendicular_to_curb']
    rows = []
    fixed_configs = []
    for suffix, entry, proof in zip(SUFFIXES, manifest['cases'], source_proof['cases']):
        assert entry['case_id'].endswith('__' + suffix)
        assert entry['case_id'] == proof['case_id']
        construction_path = PACKAGE / entry['construction']
        assert sha(construction_path) == entry['construction_sha256'] == proof['construction_sha256']
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        assert config['duration_s'] == 30 and config['rate_hz'] == 20
        assert proof['channel_frames'] == 600
        target = config['target_projection_ft']
        assert target == proof['requested_ft'] and abs(proof['measured_ft'] - target) < 0.01
        raw = PACKAGE / 'diagnostic-fixture' / suffix / 'sources/native-raw-actors.jsonl'
        assert sha(raw) == proof['raw_source_sha256']
        positive_path = PACKAGE / 'diagnostic-fixture' / suffix / 'attempt-primary-camera.log'
        saved_path = PACKAGE / 'diagnostic-fixture' / suffix / 'saved-primary-camera.log'
        positive, saved = json.loads(positive_path.read_text()), json.loads(saved_path.read_text())
        assert positive['passed'] and saved['passed'] and saved['recorded_only']
        assert positive['case_id'] == saved['case_id'] == entry['case_id']
        assert positive['construction_sha256'] == entry['construction_sha256']
        fixed = dict(config)
        for key in ('case', 'case_id', 'case_suffix', 'selected_case_id',
                    'target_projection_ft'):
            fixed.pop(key, None)
        fixed_configs.append(fixed)
        rows.append({'case_id': entry['case_id'], 'requested_ft': target,
                     'measured_ft': proof['measured_ft'], 'frames': 600,
                     'construction_sha256': entry['construction_sha256'],
                     'raw_source_sha256': proof['raw_source_sha256'],
                     'compatibility_receipt_sha256': sha(positive_path),
                     'saved_receipt_sha256': sha(saved_path)})
    assert fixed_configs[0] == fixed_configs[1] == fixed_configs[2]
    assert [row['requested_ft'] for row in rows] == [14, 15, 16]
    assert rows[0]['measured_ft'] < rows[1]['measured_ft'] < rows[2]['measured_ft']
    audit = {'format': 'c229398-synthetic-comparison-audit-v1', 'passed': True,
             'manifest_sha256': sha(MANIFEST), 'source_proof_sha256': sha(source_proof_path),
             'comparison_id': comparison['comparison_id'], 'fixed_config_sha256': hashlib.sha256(
                 json.dumps(fixed_configs[0], sort_keys=True).encode()).hexdigest(),
             'only_deliberate_config_difference': 'target_projection_ft',
             'diagnostic_only': True, 'original_native_observed': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
             'cases': rows}
    output = PACKAGE / 'diagnostic-comparison-audit.json'
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'cases': len(rows), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
