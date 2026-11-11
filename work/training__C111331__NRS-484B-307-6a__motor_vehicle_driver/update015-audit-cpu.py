"""Independently bind C111331 pair, candidate plans, and current CPU receipts."""
import hashlib
import json
import copy
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines()]


def require(test, message):
    if not test:
        raise ValueError(message)


def audit(matrix_override=None):
    manifest = load(HERE / 'draft-execution-manifest.json')
    matrix = (load(HERE / 'update015-cpu-proof-matrix.json')
              if matrix_override is None else matrix_override)
    require(len(manifest['cases']) == 2 and len(matrix['bundles']) == 8, 'Missing case or bundle')
    require(all(row['passed'] for row in matrix['bundles']), 'CPU proof matrix incomplete')
    samples = {}
    measurements = {}
    pair_knobs = {}
    for case in CASES:
        case_id = HERE.name + '__' + case
        entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
        spec = HERE / f'update015-{case}-diagnostic.json'
        recipe = load(HERE / f'update015-{case}-recipe.json')
        require(recipe['generator']['sha256'] == sha(spec) == recipe['sources'][0]['sha256'],
                'Diagnostic source hash changed')
        source = load(spec)
        require(len(source['graphs']) == 480 and len(source['videos']) == 4,
                'Diagnostic frame or camera inventory differs')
        samples[case] = rows(source['files']['native_samples.jsonl'])
        pair_knobs[case] = {}
        require(len(samples[case]) == 480 and
                all(sample['source_kind'] == 'synthetic_cpu_native_observation'
                    for sample in samples[case]), 'Native-shaped source misidentified')
        for candidate in CANDIDATES:
            label = case + '-' + candidate
            bundle = next(row for row in matrix['bundles']
                          if row['case_id'] == case_id and row['candidate_id'] == candidate)
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            construction = HERE / selected['construction']
            require(sha(construction) == selected['construction_sha256'] ==
                    bundle['construction_sha256'], 'Construction hash differs: ' + label)
            authored = load(construction)
            config = json.loads(next(item['content'] for item in authored['files']
                                     if item['path'] == 'config.json'))
            pair_knobs[case][candidate] = config['knobs']
            if candidate != 'primary':
                primary_config = pair_knobs[case]['primary']
                changed = {key for key in config['knobs']
                           if config['knobs'][key] != primary_config[key]}
                expected = {'fallback1': {'reference_red_frame', 'contrast_red_frame'},
                            'fallback2': {'speed_m_per_frame'},
                            'fallback3': {'signal_camera_fov_deg'}}[candidate]
                require(changed == expected, 'Fallback knob isolation differs: ' + label)
            for key in ('offline', 'compatibility', 'analysis_log', 'negative_log', 'process_command'):
                item = bundle[key]
                require(sha(HERE / item['path']) == item['sha256'], 'Proof file changed: ' + label)
            receipt = load(HERE / bundle['compatibility']['path'])
            require(receipt['passed'] is True and receipt['candidate_id'] == candidate and
                    receipt['case_id'] == case_id and
                    receipt['construction_sha256'] == selected['construction_sha256'] and
                    receipt['fixture_recipe_sha256'] == sha(HERE / f'update015-{case}-recipe.json') and
                    {'selected_measurements', 'negative_case_source', 'native_validation',
                     'lean_decoder', 'render', 'final_decode', 'four_camera_sources'}
                    <= set(receipt['checks']), 'Compatibility receipt incomplete: ' + label)
            require('Missing required source: native_samples.jsonl' in
                    (HERE / bundle['negative_log']['path']).read_text(),
                    'Negative did not reject exact missing source: ' + label)
            require('"recorded_only": true' in
                    (HERE / bundle['process_command']['path']).read_text().lower(),
                    'Saved processing did not report recorded-only: ' + label)
            if candidate == 'primary':
                measurements[case] = {key: value['value']
                                      for key, value in receipt['measurement_examples'].items()}
    ref, contrast = samples['reference'], samples['contrast']
    require(pair_knobs['reference'] == pair_knobs['contrast'],
            'Controlled pair candidate knobs differ')
    require(all(a['native_center_xy_m'] == b['native_center_xy_m'] and
                a['native_body_xy_m'] == b['native_body_xy_m'] and
                a['time_s'] == b['time_s'] for a, b in zip(ref, contrast)),
            'Controlled pair changed body path or time')
    require(measurements['reference']['observed_signal_phase_at_entry'] == 'yellow' and
            measurements['contrast']['observed_signal_phase_at_entry'] == 'red',
            'Controlled pair phase values differ')
    require(measurements['reference']['full_body_intersection_entry_frame'] ==
            measurements['contrast']['full_body_intersection_entry_frame'],
            'Controlled pair entry frame differs')
    return {'format': 'c111331-update015-independent-cpu-audit-v1', 'passed': True,
            'scope': 'synthetic software proof only; physical signal pixels unverified',
            'bundles': 8, 'saved_frames_per_case': 480, 'measurements': measurements,
            'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
            'matrix_sha256': sha(HERE / 'update015-cpu-proof-matrix.json')}


if __name__ == '__main__':
    report = audit()
    negative_checks = []
    for name, mutate in (
            ('changed_receipt_hash', lambda data: data['bundles'][0]['compatibility'].update(
                sha256='0' * 64)),
            ('missing_bundle', lambda data: data['bundles'].pop()),
            ('unpassed_bundle', lambda data: data['bundles'][0].update(passed=False))):
        changed = copy.deepcopy(load(HERE / 'update015-cpu-proof-matrix.json'))
        mutate(changed)
        try:
            audit(changed)
        except ValueError:
            negative_checks.append(name)
        else:
            raise ValueError('Audit accepted mutation: ' + name)
    report['negative_checks'] = negative_checks
    (HERE / 'update015-cpu-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
