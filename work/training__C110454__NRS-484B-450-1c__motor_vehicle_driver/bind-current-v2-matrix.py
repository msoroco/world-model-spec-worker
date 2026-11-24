"""Freeze six current-runtime CPU chains with their exact construction sources."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c110454-450-fallbacks'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    rows = []
    for suffix in ('probe_a', 'probe_b'):
        manifest_path = HERE / f'current-v2-{suffix}-candidate-manifest.json'
        entry = read(manifest_path)['cases'][0]
        case_id = entry['case_id']
        for candidate_id in ('primary', 'fallback1', 'fallback2'):
            selected = entry if candidate_id == 'primary' else next(
                x for x in entry['candidates'] if x['id'] == candidate_id)
            construction = HERE / selected['construction']
            assert sha(construction) == selected['construction_sha256']
            offline = SCRATCH / f'offline3-{suffix}-{candidate_id}/offline.log'
            compat_dir = SCRATCH / f'compat3-{suffix}-{candidate_id}'
            saved_dir = SCRATCH / f'saved3-{suffix}-{candidate_id}/v0001'
            compat = read(compat_dir / 'compatibility.json')
            saved = read(saved_dir / 'processing.json')
            assert compat['passed'] and compat['case_id'] == case_id
            assert compat['candidate_id'] == candidate_id
            assert compat['construction_sha256'] == sha(construction)
            assert compat['runtime_manifest_sha256'] == read(manifest_path)['runtime_manifest_sha256']
            assert compat['fixture_recipe_sha256'] == sha(HERE / f'current-v2-{suffix}-fixture-recipe.json')
            assert compat['measurement_contract_sha256'] == sha(HERE / f'current-v2-{suffix}-measurement-contract.json')
            assert {'actual_analysis', 'native_validation', 'lean_decoder', 'final_decode',
                    'four_camera_sources', 'selected_measurements', 'negative_case_source'} <= set(compat['checks'])
            assert compat['negative_error_contains'] in (compat_dir / 'negative-analysis.log').read_text()
            assert saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
            assert saved['case_id'] == case_id and saved['candidate_id'] == candidate_id
            assert saved['analysis_revision']['construction_sha256'] == sha(construction)
            assert saved['final_video_checks']['frames'] == 600
            assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
            output = HERE / f'current-v2-matrix/{suffix}/{candidate_id}'
            output.mkdir(parents=True, exist_ok=True)
            sources = {'offline.log': offline,
                       'compatibility.json': compat_dir / 'compatibility.json',
                       'public-analysis.log': compat_dir / 'compatibility-analysis.log',
                       'negative-analysis.log': compat_dir / 'negative-analysis.log',
                       'processing.json': saved_dir / 'processing.json'}
            for name, source in sources.items():
                data = source.read_text()
                assert not data.endswith('\n\n') and all(line == line.rstrip() for line in data.splitlines())
                shutil.copyfile(source, output / name)
            relation = compat['measurement_examples']['intersection_parking_footprint']['value']
            rows.append({'case_id': case_id, 'candidate_id': candidate_id,
                         'construction': selected['construction'],
                         'construction_sha256': sha(construction),
                         'manifest_sha256': sha(manifest_path),
                         'offline_log_sha256': sha(offline),
                         'compatibility_sha256': sha(sources['compatibility.json']),
                         'compatibility_log_sha256': sha(sources['public-analysis.log']),
                         'negative_log_sha256': sha(sources['negative-analysis.log']),
                         'saved_processing_sha256': sha(sources['processing.json']),
                         'parked_frames': relation['parked_frames'],
                         'sampled_intersection_overlap_m2': relation['max_intersection_body_overlap_m2'],
                         'source_only_cpu': True})
    assert len(rows) == 6
    assert {r['parked_frames'] for r in rows} == {360}
    assert {r['sampled_intersection_overlap_m2'] for r in rows if r['case_id'].endswith('__probe_a')} == {0.0}
    assert {r['sampled_intersection_overlap_m2'] for r in rows if r['case_id'].endswith('__probe_b')} == {11.44}
    proof = {'format': 'c110454-current-v2-six-chain-proof', 'passed': True,
             'selected': False, 'physical_acceptance_claimed': False,
             'legal_acceptance_claimed': False, 'rows': rows,
             'controlled_difference': 'sampled parked-body overlap 0 versus 11.44 square metres',
             'limitations': 'Synthetic source-shaped CPU packets only; no original CARLA motion or pixels'}
    path = HERE / 'current-v2-six-chain-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'chains': len(rows), 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
