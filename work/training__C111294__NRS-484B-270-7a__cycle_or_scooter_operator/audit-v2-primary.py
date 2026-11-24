"""Independently verify returned current-runtime primary proof bindings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(case):
    manifest_path = HERE / ('v2-primary-' + case + '-manifest.json')
    manifest = read(manifest_path)
    assert manifest['format'] == 'worker-execution-manifest'
    assert manifest['status'] == 'unselected_current_v2_cpu_primary_proof'
    assert len(manifest['cases']) == 1
    entry = manifest['cases'][0]
    assert entry['case_id'] == HERE.name + '__' + case
    assert entry['kind'] == 'unselected_cpu_diagnostic'
    assert not entry['candidates']
    construction_path = HERE / entry['construction']
    assert sha(construction_path) == entry['construction_sha256']
    construction = read(construction_path)
    assert construction['case_id'] == entry['case_id']
    assert construction['law_id'] == 'NRS-484B-270-7a'
    assert construction['cell_id'] == 'C111294'
    assert construction['actor'] == 'cycle_or_scooter_operator'
    files = {item['path']: item['content'] for item in construction['files']}
    config = json.loads(files['config.json'])
    assert config['duration_s'] == 30 and config['rate_hz'] == 20
    assert set(config['knobs']['camera_profile']) == {
        'overview', 'approach', 'reference_corner', 'driver_reference'}
    recipe_path = ROOT / entry['fixture_recipe']
    recipe = read(recipe_path)
    generator = read(ROOT / recipe['generator']['source'])
    assert sha(ROOT / recipe['generator']['source']) == recipe['generator']['sha256']
    assert len(generator['graphs']) == 600
    assert len(generator['videos']) == 4
    assert all(item['frames'] == 600 for item in generator['videos'])
    assert len(recipe['sources']) == 10
    for item in recipe['sources']:
        assert sha(ROOT / item['source']) == item['sha256']
    proofs = HERE / 'v2-primary' / case / 'proofs'
    compat = read(proofs / 'compatibility.json')
    saved = read(proofs / 'processing.json')
    selection = read(proofs / 'candidate-selection.json')
    assert compat['passed'] and CHECKS <= set(compat['checks'])
    assert compat['case_id'] == entry['case_id'] and compat['candidate_id'] == 'primary'
    assert compat['construction_sha256'] == sha(construction_path)
    assert compat['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert compat['fixture_recipe_sha256'] == sha(recipe_path)
    assert compat['negative_removed'] == 'interaction.json'
    assert compat['negative_error_contains'] in (proofs / 'negative.log').read_text()
    assert compat['log_sha256'] == sha(proofs / 'analysis.log')
    assert compat['negative_log_sha256'] == sha(proofs / 'negative.log')
    assert 'Ran ' in (proofs / 'offline.log').read_text()
    assert selection['manifest_sha256'] == sha(manifest_path)
    assert selection['construction_sha256'] == sha(construction_path)
    assert saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
    assert not saved['missing_evidence']
    assert saved['timestamp_joins']['frames'] == 600
    assert saved['final_video_checks']['passed']
    assert saved['original_source_hashes']['candidate-selection.json'] == sha(proofs / 'candidate-selection.json')
    assert saved['analysis_revision']['construction_sha256'] == sha(construction_path)
    assert saved['analysis_revision']['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
    return {'case': case, 'manifest_sha256': sha(manifest_path),
            'construction_sha256': sha(construction_path), 'recipe_sha256': sha(recipe_path),
            'compatibility_sha256': sha(proofs / 'compatibility.json'),
            'processing_sha256': sha(proofs / 'processing.json'),
            'frames': 600, 'negative_removed': 'interaction.json'}


def main():
    rows = [audit(case) for case in ('witness_1', 'witness_2')]
    result = {'format': 'c111294-unselected-v2-primary-audit', 'passed': True,
              'selected': False, 'cases': rows, 'physical_observation': False,
              'legal_verdict': None}
    path = HERE / 'v2-primary' / 'audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'primaries': len(rows), 'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()
