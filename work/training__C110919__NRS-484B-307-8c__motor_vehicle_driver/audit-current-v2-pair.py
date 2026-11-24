"""Bind exact current-runtime red-right-turn diagnostic positives and negatives."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = []
    for suffix, letter in [('probe_a','a'), ('probe_b','b')]:
        manifest = HERE / f'current-v2-{suffix}-primary-manifest.json'
        recipe = HERE / f'current-v2-{suffix}-fixture-recipe.json'
        contract = HERE / f'current-v2-{suffix}-measurement-contract.json'
        entry = json.loads(manifest.read_text())['cases'][0]
        construction = HERE / entry['construction']
        compat_dir = ROOT / f'.runtime-work/c110919-v2-probe-{letter}-compat-001'
        saved_dir = ROOT / f'.runtime-work/c110919-v2-probe-{letter}-saved-001/v0001'
        compat = json.loads((compat_dir / 'compatibility.json').read_text())
        saved = json.loads((saved_dir / 'processing.json').read_text())
        assert entry['construction_sha256'] == sha(construction)
        assert entry['fixture_recipe'] == recipe.relative_to(ROOT).as_posix()
        assert entry['measurement_contract'] == contract.name
        assert compat['passed'] and compat['case_id'] == entry['case_id']
        assert compat['construction_sha256'] == sha(construction)
        assert compat['fixture_recipe_sha256'] == sha(recipe)
        assert compat['measurement_contract_sha256'] == sha(contract)
        assert {'four_camera_sources','lean_decoder','final_decode',
                'selected_measurements','negative_case_source'} <= set(compat['checks'])
        assert compat['negative_removed'] == 'road_geometry.json'
        assert compat['negative_error_contains'] in (compat_dir / 'negative-analysis.log').read_text()
        assert saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
        assert saved['final_video_checks']['frames'] == 600
        assert saved['case_id'] == entry['case_id']
        assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
        for name, source in [('compatibility',compat_dir / 'compatibility.json'),
                             ('negative-analysis',compat_dir / 'negative-analysis.log'),
                             ('processing',saved_dir / 'processing.json')]:
            extension = 'log' if name == 'negative-analysis' else 'json'
            shutil.copyfile(source, HERE / f'current-v2-{suffix}-{name}.{extension}')
        measurement = compat['measurement_examples']['red_right_turn_permission']['value']
        cases.append({'case_id': entry['case_id'], 'manifest_sha256': sha(manifest),
                      'construction_sha256': sha(construction), 'recipe_sha256': sha(recipe),
                      'contract_sha256': sha(contract),
                      'compatibility_sha256': sha(compat_dir / 'compatibility.json'),
                      'negative_log_sha256': sha(compat_dir / 'negative-analysis.log'),
                      'saved_processing_sha256': sha(saved_dir / 'processing.json'),
                      'pre_turn_full_halt': measurement['pre_turn_full_halt'],
                      'stationary_frames': measurement['pre_crossing_stationary_frames'],
                      'steady_red_frames': measurement['steady_red_frames'],
                      'pedestrian_clearance_s': measurement['pedestrian_clearance_s'],
                      'other_traffic_clearance_s': measurement['other_traffic_clearance_s'],
                      'final_decoded_frames': saved['final_video_checks']['frames']})
    assert [case['pre_turn_full_halt'] for case in cases] == [True,False]
    assert [case['stationary_frames'] for case in cases] == [30,0]
    for key in ('steady_red_frames','pedestrian_clearance_s','other_traffic_clearance_s'):
        assert cases[0][key] == cases[1][key]
    proof = {'format':'c110919-current-v2-600-pair-proof-v1', 'passed':True,
             'selected':False, 'physical_acceptance_claimed':False,
             'controlled_difference':'pre-turn full halt under steady red',
             'cases':cases,
             'scope':'synthetic Native/software measurements only; no original motion, visible pixels or legal permission'}
    output = HERE / 'current-v2-primary-pair-proof.json'
    output.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'proof_sha256':sha(output),'cases':len(cases),'passed':True}))


if __name__ == '__main__':
    main()
