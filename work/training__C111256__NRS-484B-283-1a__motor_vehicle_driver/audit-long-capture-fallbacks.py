"""Independently bind every current 600-frame fallback runtime receipt."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111256-fallbacks'
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CANDIDATES = ('fallback1', 'fallback2', 'fallback3')
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(case, candidate):
    manifest_path = HERE / f'long-capture-fallbacks-{case}-manifest.json'
    manifest = read(manifest_path)
    assert manifest['status'] == 'unselected_30_second_cpu_fallback_migration'
    assert len(manifest['cases']) == 1
    entry = manifest['cases'][0]
    assert entry['case_id'] == HERE.name + '__' + case
    selected = next(item for item in entry['candidates'] if item['id'] == candidate)
    construction_path = HERE / selected['construction']
    assert sha(construction_path) == selected['construction_sha256']
    construction = read(construction_path)
    assert construction['case_id'] == entry['case_id']
    assert construction['cell_id'] == 'C111256'
    files = {item['path']: item['content'] for item in construction['files']}
    config = json.loads(files['config.json'])
    assert config['duration_s'] == 30 and config['rate_hz'] == 20
    assert config['candidate_id'] == candidate
    assert {item['name'] for item in config['cameras']} == {
        'overview', 'approach', 'reference_corner', 'driver_reference'}
    scratch = SCRATCH / (case + '-' + candidate)
    offline = (scratch / 'offline/offline.log').read_text()
    assert 'Ran 5 tests' in offline and '\nOK\n' in offline
    compat_path = scratch / 'compat/compatibility.json'
    compat = read(compat_path)
    assert compat['passed'] and compat['case_id'] == entry['case_id']
    assert compat['candidate_id'] == candidate
    assert compat['construction_sha256'] == sha(construction_path)
    assert compat['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert compat['negative_removed'] == 'road_geometry.json'
    assert CHECKS <= set(compat['checks'])
    recipe = ROOT / entry['fixture_recipe']
    assert compat['fixture_recipe_sha256'] == sha(recipe)
    saved_path = scratch / 'saved/v0001/processing.json'
    saved = read(saved_path)
    assert saved['passed'] and saved['case_id'] == entry['case_id']
    assert saved['candidate_id'] == candidate
    assert saved['analysis_revision']['construction_sha256'] == sha(construction_path)
    assert saved['analysis_revision']['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert saved['timestamp_joins']['frames'] == 600
    assert saved['originals_preserved'] and not saved['missing_evidence']
    assert saved['final_video_checks']['passed']
    assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
    selection_path = scratch / 'compat/candidate-selection.json'
    selection = read(selection_path)
    assert selection['manifest_sha256'] == sha(manifest_path)
    assert selection['construction_sha256'] == selected['construction_sha256']
    assert saved['original_source_hashes']['candidate-selection.json'] == sha(selection_path)
    return {'case': case, 'candidate': candidate,
            'construction_sha256': sha(construction_path),
            'manifest_sha256': sha(manifest_path),
            'recipe_sha256': sha(recipe),
            'compatibility_sha256': sha(compat_path),
            'saved_sha256': sha(saved_path),
            'negative_removed': 'road_geometry.json',
            'frames': 600, 'originals_preserved': True}


def main():
    rows = [audit(case, candidate) for case in CASES for candidate in CANDIDATES]
    result = {'format': 'c111256-unselected-600-frame-fallback-audit',
              'passed': True, 'selected': False, 'cases': rows,
              'physical_observation': False, 'legal_verdict': None}
    path = HERE / 'long-capture-fallbacks' / 'audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'candidates': len(rows),
                      'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()
