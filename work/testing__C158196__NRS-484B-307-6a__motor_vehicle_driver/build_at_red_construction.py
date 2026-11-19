"""Bind the second exact yellow/red case without replacing the first case."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__entry_at_red'
REL = Path('cases/entry_at_red/construction.json')
CONTRACT = Path('cases/entry_at_red/measurement-contract.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if len(manifest['cases']) not in (1, 2) or manifest['cases'][0]['case_id'] != HERE.name + '__entry_before_red':
        raise ValueError('Unexpected existing exact-case manifest; preserve prior work')
    construction = deepcopy(json.loads((HERE / 'construction.json').read_text()))
    construction['case_id'] = CASE
    construction['measurement_plan']['saved_processing_status'] = 'pending_exact_case_proof'
    for entry in construction['files']:
        if entry['path'] == 'config.json':
            config = json.loads(entry['content'])
            config['selected_case_id'] = CASE
            config['case']['case_id'] = CASE
            entry['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
            break
    else:
        raise ValueError('First construction did not include inline configuration')
    write(HERE / REL, construction)
    contract = deepcopy(json.loads((HERE / 'measurement-contract.json').read_text()))
    contract['case_id'] = CASE
    write(HERE / CONTRACT, contract)
    first = manifest['cases'][0]
    second = {
        'case_id': CASE, 'kind': 'delivery', 'construction': str(REL),
        'construction_sha256': sha(HERE / REL),
        'candidate_risk': deepcopy(first['candidate_risk']), 'candidates': [],
        'measurement_contract': str(CONTRACT),
        'measurement_procedure': deepcopy(first['measurement_procedure']),
        'native_handoff': deepcopy(first['native_handoff']),
        'acquisition': deepcopy(first['acquisition']),
    }
    recipe = HERE / 'at-red-fixture-recipe.json'
    if recipe.is_file():
        second['fixture_recipe'] = 'work/' + HERE.name + '/' + recipe.name
    offline_log = HERE / 'at-red-offline.log'
    if offline_log.is_file():
        second['offline'] = {
            'command': ('.venv-cpu/bin/python runtime.py offline --manifest work/' +
                        HERE.name + '/execution-manifest.json --case ' + CASE +
                        ' --output .runtime-work/c158196-yellow-red-at-red-offline'),
            'construction_sha256': sha(HERE / REL), 'exit_code': 0,
            'log': offline_log.name, 'log_sha256': sha(offline_log)}
    compatibility = HERE / 'at-red-compatibility.json'
    if compatibility.is_file():
        second['compatibility'] = {
            'receipt': compatibility.name, 'sha256': sha(compatibility),
            'log': 'at-red-compatibility-analysis.log',
            'replay_command': ('.venv-cpu/bin/python runtime.py compatibility --manifest work/' +
                               HERE.name + '/execution-manifest.json --case ' + CASE +
                               ' --output .runtime-work/c158196-yellow-red-at-red-compatibility' +
                               ' --library runtime/library --validator ' +
                               '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')}
        second['negative'] = {'log': 'at-red-negative-analysis.log'}
    if len(manifest['cases']) == 1:
        manifest['cases'].append(second)
    else:
        for key in second:
            manifest['cases'][1][key] = second[key]
    write(manifest_path, manifest)
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(HERE / REL),
                      'manifest_sha256': sha(manifest_path), 'status': 'draft'}))


if __name__ == '__main__':
    main()
