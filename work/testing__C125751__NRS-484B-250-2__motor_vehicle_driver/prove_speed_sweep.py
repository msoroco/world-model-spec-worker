"""Reproduce the C125751 diagnostic subject-speed judgment sweep.

These are engineering speed targets on a synthetic site, not legal cutoffs or
proof that Native actors reach the requested speed.
"""
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SPEEDS = (3.5, 5.0, 6.5)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, document):
    Path(path).write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')


def config_of(construction):
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


def fixed_conditions(constructions):
    normalized = []
    for construction, speed in zip(constructions, SPEEDS):
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        if config.get('ego_target_speed_mps') != speed or config.get('other_target_speed_mps') != 5:
            raise ValueError('Declared speed axis or fixed opposing speed differs')
        config.pop('ego_target_speed_mps')
        files['config.json'] = json.dumps(config, sort_keys=True)
        normalized.append((construction['case_id'], construction['recording_description'], files))
    if any(value != normalized[0] for value in normalized[1:]):
        raise ValueError('Speed sweep changed another construction condition')
    mutated = copy.deepcopy(constructions[0])
    entry = next(item for item in mutated['files'] if item['path'] == 'config.json')
    config = json.loads(entry['content'])
    config['other_target_speed_mps'] = 4.0
    entry['content'] = json.dumps(config)
    try:
        fixed_conditions_without_negative([mutated, *constructions[1:]])
    except ValueError as error:
        if 'fixed opposing speed differs' not in str(error):
            raise
    else:
        raise ValueError('Changed fixed opposing speed escaped')
    return True


def fixed_conditions_without_negative(constructions):
    for construction, speed in zip(constructions, SPEEDS):
        config = config_of(construction)
        if config.get('ego_target_speed_mps') != speed or config.get('other_target_speed_mps') != 5:
            raise ValueError('Declared speed axis or fixed opposing speed differs')


def run(command, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with Path(log).open('w') as output:
        finished = subprocess.run(command, cwd=REPO, env=env, stdout=output,
                                  stderr=subprocess.STDOUT, check=False)
    if finished.returncode:
        raise ValueError(f'CPU proof failed ({finished.returncode}): {log}')
    return {'command': command, 'exit_code': 0, 'log': str(log), 'log_sha256': sha(log)}


def prove(output_root):
    root = Path(output_root).resolve()
    if root.exists():
        raise ValueError('Preserve prior proof; choose a fresh output root')
    root.mkdir(parents=True)
    for name in ('case-plan.json', 'measurement-contract.json'):
        (root / name).write_bytes((HERE / name).read_bytes())
    (root / 'proposals').mkdir()
    (root / 'proposals/cases.json').write_bytes((HERE / 'proposals/cases.json').read_bytes())
    source_manifest = json.loads((HERE / 'candidate-proof-manifest-v2.json').read_text())
    case = next(item for item in source_manifest['cases']
                if item['case_id'].endswith('__signal_off'))
    base = json.loads((HERE / case['construction']).read_text())
    constructions, receipts = [], []
    runtime = str(REPO / 'runtime.py')
    python = sys.executable
    validator = str(REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')
    if not Path(validator).is_file():
        raise ValueError('Existing saved-processing Lean validator missing')
    for speed in SPEEDS:
        label = str(speed).replace('.', '_')
        construction = copy.deepcopy(base)
        entry = next(item for item in construction['files'] if item['path'] == 'config.json')
        config = json.loads(entry['content'])
        config['ego_target_speed_mps'] = speed
        entry['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        constructions.append(construction)
        construction_path = root / f'construction-speed-{label}.json'
        dump(construction_path, construction)
        manifest = {'format': 'worker-execution-manifest',
                    'assignment_id': HERE.name,
                    'runtime_manifest_sha256': source_manifest['runtime_manifest_sha256'],
                    'cases': [{'case_id': case['case_id'], 'kind': 'delivery',
                               'construction': construction_path.name,
                               'construction_sha256': sha(construction_path),
                               'fixture_recipe': case['fixture_recipe'],
                               'measurement_procedure': case['measurement_procedure'],
                               'measurement_contract': case['measurement_contract']}]}
        manifest_path = root / f'manifest-speed-{label}.json'
        dump(manifest_path, manifest)
        prefix = [python, runtime]
        common = ['--manifest', str(manifest_path), '--case', case['case_id']]
        proofs = []
        proofs.append(run(prefix + ['offline', *common, '--output', str(root / f'{label}-offline')],
                          root / f'{label}-offline.log'))
        proofs.append(run(prefix + ['compatibility', *common, '--output', str(root / f'{label}-compat'),
                                    '--library', str(REPO / 'runtime/library'),
                                    '--validator', validator], root / f'{label}-compat.log'))
        proofs.append(run(prefix + ['process-saved', *common, '--attempt', str(root / f'{label}-compat'),
                                    '--output', str(root / f'{label}-saved'),
                                    '--library', str(REPO / 'runtime/library'),
                                    '--validator', validator], root / f'{label}-saved.log'))
        receipts.append({'ego_target_speed_mps': speed,
                         'other_target_speed_mps': 5,
                         'construction_sha256': sha(construction_path),
                         'manifest_sha256': sha(manifest_path), 'proofs': proofs})
    fixed_conditions(constructions)
    result = {'format': 'worker-c125751-diagnostic-speed-sweep',
              'case_id': case['case_id'], 'source_construction_sha256': sha(HERE / case['construction']),
              'source_manifest_sha256': sha(HERE / 'candidate-proof-manifest-v2.json'),
              'speed_axis_mps': list(SPEEDS), 'receipts': receipts,
              'only_subject_speed_varied': True, 'changed_fixed_opposing_speed_rejected': True,
              'native_speed_response_proven': False, 'legal_yield_claimed': False,
              'physical_acceptance_claimed': False}
    dump(root / 'proof.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', required=True)
    arguments = parser.parse_args()
    result = prove(arguments.output_root)
    print(json.dumps({'variants': len(result['receipts']), 'passed': True,
                      'proof': str(Path(arguments.output_root) / 'proof.json')}))
