"""Verify all returned current v2 fallback construction and receipt bindings."""
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


def audit(case, candidate):
    manifest_path = HERE / ('v2-fallbacks-' + case + '-manifest.json')
    manifest = read(manifest_path)
    assert manifest['status'] == 'unselected_current_v2_cpu_fallback_proof'
    assert len(manifest['cases']) == 1
    entry = manifest['cases'][0]
    assert entry['case_id'] == HERE.name + '__' + case
    selected = next(item for item in entry['candidates'] if item['id'] == candidate)
    construction_path = HERE / selected['construction']
    assert selected['construction_sha256'] == sha(construction_path)
    construction = read(construction_path)
    assert construction['case_id'] == entry['case_id']
    assert (construction['law_id'], construction['cell_id'], construction['actor']) == (
        'NRS-484B-270-7a', 'C111294', 'cycle_or_scooter_operator')
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    assert config['duration_s'] == 30 and config['rate_hz'] == 20
    assert set(config['knobs']['camera_profile']) == {
        'overview', 'approach', 'reference_corner', 'driver_reference'}
    primary = read(HERE / entry['construction'])
    primary_config = json.loads(next(item['content'] for item in primary['files']
                                     if item['path'] == 'config.json'))
    assert (config['case_id'], config['law_id'], config['cell_id'], config['actor']) == (
        primary_config['case_id'], primary_config['law_id'],
        primary_config['cell_id'], primary_config['actor'])
    changed = {key for key in config['knobs'] if config['knobs'][key] != primary_config['knobs'][key]}
    assert changed == set(selected['changed_knobs']) and len(changed) == 1
    recipe_path = ROOT / entry['fixture_recipe']
    recipe = read(recipe_path)
    assert sha(ROOT / recipe['generator']['source']) == recipe['generator']['sha256']
    for source in recipe['sources']:
        assert sha(ROOT / source['source']) == source['sha256']
    proof = HERE / 'v2-fallbacks' / case / candidate / 'proofs'
    compat = read(proof / 'compatibility.json')
    saved = read(proof / 'processing.json')
    selection = read(proof / 'candidate-selection.json')
    assert compat['passed'] and CHECKS <= set(compat['checks'])
    assert compat['case_id'] == entry['case_id'] and compat['candidate_id'] == candidate
    assert compat['construction_sha256'] == sha(construction_path)
    assert compat['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert compat['fixture_recipe_sha256'] == sha(recipe_path)
    assert compat['negative_removed'] == 'interaction.json'
    assert compat['negative_error_contains'] in (proof / 'negative.log').read_text()
    assert compat['log_sha256'] == sha(proof / 'analysis.log')
    assert compat['negative_log_sha256'] == sha(proof / 'negative.log')
    assert 'Ran ' in (proof / 'offline.log').read_text()
    assert selection['manifest_sha256'] == sha(manifest_path)
    assert selection['construction_sha256'] == sha(construction_path)
    assert saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
    assert not saved['missing_evidence']
    assert saved['candidate_id'] == candidate and saved['timestamp_joins']['frames'] == 600
    assert saved['final_video_checks']['passed']
    assert saved['original_source_hashes']['candidate-selection.json'] == sha(proof / 'candidate-selection.json')
    assert saved['analysis_revision']['construction_sha256'] == sha(construction_path)
    assert saved['analysis_revision']['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
    return {'case': case, 'candidate': candidate, 'manifest_sha256': sha(manifest_path),
            'construction_sha256': sha(construction_path), 'compatibility_sha256': sha(proof / 'compatibility.json'),
            'processing_sha256': sha(proof / 'processing.json'), 'frames': 600,
            'changed_knobs': sorted(changed)}


def main():
    rows = [audit(case, candidate) for case in ('witness_1', 'witness_2')
            for candidate in ('fallback1', 'fallback2', 'fallback3')]
    result = {'format': 'c111294-unselected-v2-fallback-audit', 'passed': True,
              'selected': False, 'cases': rows, 'physical_observation': False,
              'legal_verdict': None}
    path = HERE / 'v2-fallbacks' / 'audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'fallbacks': len(rows), 'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()
