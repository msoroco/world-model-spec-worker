"""Bind the two current-runtime synthetic CPU receipts and their controlled contrast."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = []
    for suffix, letter, compat_no in [('probe_a', 'a', '006'), ('probe_b', 'b', '002')]:
        manifest = HERE / f'current-v2-{suffix}-primary-manifest.json'
        recipe = HERE / f'current-v2-{suffix}-fixture-recipe.json'
        contract = HERE / f'current-v2-{suffix}-measurement-contract.json'
        construction = HERE / f'current-v2-{suffix}-primary-construction.json'
        compat_dir = SCRATCH / f'c110454-v2-probe-{letter}-compat-{compat_no}'
        saved_dir = SCRATCH / f'c110454-v2-probe-{letter}-saved-002/v0001'
        compat = json.loads((compat_dir / 'compatibility.json').read_text())
        saved = json.loads((saved_dir / 'processing.json').read_text())
        entry = json.loads(manifest.read_text())['cases'][0]
        assert entry['construction_sha256'] == sha(construction)
        assert entry['fixture_recipe'] == recipe.relative_to(ROOT).as_posix()
        assert entry['measurement_contract'] == contract.name
        assert compat['passed'] and compat['case_id'] == entry['case_id']
        assert compat['construction_sha256'] == sha(construction)
        assert compat['fixture_recipe_sha256'] == sha(recipe)
        assert compat['measurement_contract_sha256'] == sha(contract)
        assert {'four_camera_sources', 'lean_decoder', 'final_decode',
                'selected_measurements', 'negative_case_source'} <= set(compat['checks'])
        assert compat['negative_removed'] == 'native_samples.jsonl'
        assert compat['negative_error_contains'] in (compat_dir / 'negative-analysis.log').read_text()
        assert saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
        assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
        assert saved['final_video_checks']['frames'] == 600
        assert saved['case_id'] == entry['case_id']
        config = json.loads(next(item['content'] for item in json.loads(construction.read_text())['files']
                                 if item['path'] == 'config.json'))
        assert [camera['name'] for camera in config['cameras']] == [
            'overview', 'approach', 'reference_corner', 'driver_reference']
        for name, source in [('compatibility', compat_dir / 'compatibility.json'),
                             ('negative-analysis', compat_dir / 'negative-analysis.log'),
                             ('processing', saved_dir / 'processing.json')]:
            shutil.copyfile(source, HERE / f'current-v2-{suffix}-{name}.{ "log" if name == "negative-analysis" else "json"}')
        relation = compat['measurement_examples']['intersection_parking_footprint']['value']
        cases.append({'case_id': entry['case_id'], 'manifest_sha256': sha(manifest),
                      'construction_sha256': sha(construction), 'recipe_sha256': sha(recipe),
                      'contract_sha256': sha(contract),
                      'compatibility_sha256': sha(compat_dir / 'compatibility.json'),
                      'negative_log_sha256': sha(compat_dir / 'negative-analysis.log'),
                      'saved_processing_sha256': sha(saved_dir / 'processing.json'),
                      'source_frames': saved['final_video_checks']['frames'],
                      'parked_frames': relation['parked_frames'],
                      'parking_relation': relation['parking_relation'],
                      'sampled_intersection_overlap_m2': relation['max_intersection_body_overlap_m2']})
    assert [(c['parking_relation'], c['sampled_intersection_overlap_m2']) for c in cases] == [
        ('outside_intersection', 0.0), ('within_intersection', 11.44)]
    proof = {'format': 'c110454-current-v2-600-pair-proof-v1', 'passed': True,
             'selected': False, 'physical_acceptance_claimed': False,
             'cases': cases, 'controlled_difference': 'parking footprint inside versus outside intersection',
             'scope': '600-frame synthetic Native/software path; no original motion or pixel visibility'}
    output = HERE / 'current-v2-primary-pair-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(output), 'cases': len(cases), 'passed': True}))


if __name__ == '__main__':
    main()
