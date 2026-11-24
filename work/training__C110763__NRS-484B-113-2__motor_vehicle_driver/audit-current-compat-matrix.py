"""Independently bind eight current-runtime strict diagnostic compatibility receipts."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'current-compat-matrix-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    runtime_sha = json.loads((REPO / 'batch.json').read_text())['runtime']['source_manifest_sha256']
    if manifest['runtime_manifest_sha256'] != runtime_sha:
        raise ValueError('Manifest binds another runtime')
    entries = {e['case_id'].split('__')[-1]: e for e in manifest['cases']}
    if set(entries) != {'probe_1', 'probe_2'}:
        raise ValueError('Controlled exact cases differ')
    outputs = {}
    configs = {}
    for suffix, label in (('probe_1', 'a'), ('probe_2', 'b')):
        entry = entries[suffix]
        recipe_path = REPO / entry['fixture_recipe']
        recipe = json.loads(recipe_path.read_text())
        generator = REPO / recipe['generator']['source']
        if sha(generator) != recipe['generator']['sha256']:
            raise ValueError('Source generator changed')
        refs = [{'id': 'primary', 'construction': entry['construction'],
                 'construction_sha256': entry['construction_sha256']}] + entry['candidates']
        for ref in refs:
            candidate = ref['id']
            construction_path = HERE / ref['construction']
            if sha(construction_path) != ref['construction_sha256']:
                raise ValueError('Construction changed: ' + suffix + '/' + candidate)
            construction = json.loads(construction_path.read_text())
            config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
            if candidate == 'primary':
                configs[suffix] = config
            output = REPO / '.runtime-work' / f'c110763-current-matrix-{label}-{candidate}'
            receipt_path = output / 'compatibility.json'
            receipt = json.loads(receipt_path.read_text())
            if (receipt['format'] != 'worker-package-compatibility' or receipt['passed'] is not True
                    or receipt['case_id'] != entry['case_id'] or receipt['candidate_id'] != candidate
                    or receipt['construction_sha256'] != ref['construction_sha256']
                    or receipt['runtime_manifest_sha256'] != runtime_sha
                    or receipt['fixture_recipe_sha256'] != sha(recipe_path)
                    or not CHECKS <= set(receipt['checks'])):
                raise ValueError('Exact compatibility binding differs: ' + suffix + '/' + candidate)
            if sha(output / 'compatibility-analysis.log') != receipt['log_sha256']:
                raise ValueError('Analysis log changed')
            if sha(output / 'negative-analysis.log') != receipt['negative_log_sha256']:
                raise ValueError('Negative log changed')
            if receipt['negative_removed'] != 'native_samples.jsonl' or \
                    receipt['negative_error_contains'] not in (output / 'negative-analysis.log').read_text():
                raise ValueError('Missing-source rejection absent')
            decode = json.loads((output / 'final-decode.json').read_text())
            if decode.get('passed') is not True or decode.get('frames') != 600:
                raise ValueError('Full final video decode absent')
            measured = receipt['measurement_examples']['backing_intersection_relation']
            relation = 'backing_clear_of_intersection' if suffix == 'probe_1' else 'backing_into_intersection'
            if measured['value']['relation'] != relation or measured['value']['backing_frames'] != 200:
                raise ValueError('Source-derived intersection relation differs')
            outputs[suffix + '/' + candidate] = {'construction_sha256': ref['construction_sha256'],
                'compatibility_sha256': sha(receipt_path),
                'log_sha256': sha(HERE / f'current-matrix-{label}-{candidate}.log'),
                'relation': relation,
                'max_overlap_m2': measured['value']['max_backing_intersection_overlap_m2']}
    a, b = configs['probe_1'], configs['probe_2']
    for key in ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'required_atoms',
                'source_packets', 'mandatory_channels', 'recording_description', 'cameras',
                'engineering_knobs'):
        if a[key] != b[key]:
            raise ValueError('Fixed controlled condition differs: ' + key)
    generators = [json.loads((HERE / name).read_text()) for name in
                  ('current-600-primary-generator.json', 'current-600-controlled-generator.json')]
    rows = [[json.loads(line) for line in item['files']['native_samples.jsonl'].splitlines()]
            for item in generators]
    if len(rows[0]) != 600 or len(rows[1]) != 600:
        raise ValueError('Full source rows absent')
    for first, second in zip(*rows):
        for key in ('video_frame', 'native_frame', 'time_s', 'native_forward_xy', 'heading_deg',
                    'native_intersection_survey', 'intersection_polygon_xy_m'):
            if first[key] != second[key]:
                raise ValueError('Controlled source differs outside intended reverse path: ' + key)
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if outputs['probe_1/' + candidate]['max_overlap_m2'] != 0 or \
                outputs['probe_2/' + candidate]['max_overlap_m2'] <= 3:
            raise ValueError('Controlled backing footprint contrast absent')
    proof = {'format': 'c110763-current-compatibility-matrix-v1', 'passed': True,
             'scope': 'synthetic current-runtime software compatibility only',
             'physical_observation_claimed': False, 'legal_verdict': None,
             'manifest_sha256': sha(manifest_path), 'runtime_manifest_sha256': runtime_sha,
             'cases': 2, 'candidate_paths': len(outputs), 'frames_per_path': 600,
             'fixed_conditions_checked': True, 'source_row_pair_checked': 600,
             'receipts': outputs}
    proof_path = HERE / 'current-compat-matrix-audit.json'
    proof_path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'paths': len(outputs), 'proof_sha256': sha(proof_path)}, sort_keys=True))


if __name__ == '__main__':
    main()
