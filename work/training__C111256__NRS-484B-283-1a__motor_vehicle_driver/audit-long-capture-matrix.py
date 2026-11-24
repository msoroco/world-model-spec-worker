"""Independently bind four unselected 30-second current-runtime CPU probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111256-matrix'
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case):
    folder = HERE / 'long-capture-matrix' / case
    manifest_path = HERE / f'long-capture-matrix-{case}-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['status'] == 'unselected_30_second_cpu_migration_prototype'
    assert len(manifest['cases']) == 1
    entry = manifest['cases'][0]
    assert entry['case_id'] == HERE.name + '__' + case
    construction_path = folder / 'construction.json'
    assert entry['construction_sha256'] == sha(construction_path)
    construction = json.loads(construction_path.read_text())
    files = {item['path']: item['content'] for item in construction['files']}
    config = json.loads(files['config.json'])
    assert config['rate_hz'] == 20 and config['duration_s'] == 30
    assert {item['name'] for item in config['cameras']} == CAMERAS
    generator_path = folder / 'diagnostic-generator.json'
    generator = json.loads(generator_path.read_text())
    assert len(generator['graphs']) == 600
    assert {item['path'] for item in generator['videos']} == {
        name + '.mkv' for name in CAMERAS}
    assert all(item['frames'] == 600 and item['fps'] == 20 for item in generator['videos'])
    recipe_path = folder / 'diagnostic-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    assert recipe['generator']['sha256'] == sha(generator_path)
    assert entry['fixture_recipe'] == str(recipe_path.relative_to(ROOT))
    offline_path = SCRATCH / f'offline-{case}/offline.log'
    offline = offline_path.read_text()
    assert 'Ran 5 tests' in offline and '\nOK\n' in offline
    assert '"native_imported": false' in offline
    compat_path = SCRATCH / f'compat-{case}/compatibility.json'
    compat = json.loads(compat_path.read_text())
    assert compat['passed'] is True and compat['case_id'] == entry['case_id']
    assert compat['construction_sha256'] == sha(construction_path)
    assert compat['fixture_recipe_sha256'] == sha(recipe_path)
    assert compat['negative_removed'] == 'road_geometry.json'
    assert {'four_camera_sources', 'selected_measurements', 'negative_case_source',
            'derived_outputs_rebuilt'} <= set(compat['checks'])
    saved_path = SCRATCH / f'saved-{case}/v0001/processing.json'
    saved = json.loads(saved_path.read_text())
    assert saved['passed'] and saved['case_id'] == entry['case_id']
    assert saved['timestamp_joins'] == {'frames': 600, 'passed': True,
                                       'missing_original_trace_or_map': False}
    assert saved['originals_preserved'] and not saved['missing_evidence']
    assert saved['final_video_checks']['passed']
    assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
    return {'case_id': entry['case_id'], 'construction_sha256': sha(construction_path),
            'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
            'generator_sha256': sha(generator_path),
            'offline_sha256': sha(offline_path),
            'compatibility_sha256': sha(compat_path), 'saved_sha256': sha(saved_path),
            'frames': 600, 'camera_count': 4, 'negative_removed': 'road_geometry.json'}


if __name__ == '__main__':
    rows = [audit(case) for case in CASES]
    result = {'format': 'c111256-unselected-30-second-matrix-audit-v1',
              'passed': True, 'cases': rows, 'physical_claim': False,
              'legal_verdict': None, 'selected': False}
    target = HERE / 'long-capture-matrix-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_count': len(rows),
                      'audit_sha256': sha(target)}))
