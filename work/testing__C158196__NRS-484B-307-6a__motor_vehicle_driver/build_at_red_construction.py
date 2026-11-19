"""Bind an additional exact yellow/red entry case, preserving existing cases."""
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('entry_at_red', 'entry_after_red', 'stops_on_yellow'), default='entry_at_red')
    args = parser.parse_args()
    suffix = args.case
    case = HERE.name + '__' + suffix
    rel = Path('cases') / suffix / 'construction.json'
    contract_path = Path('cases') / suffix / 'measurement-contract.json'
    stem = {'entry_at_red': 'at-red', 'entry_after_red': 'after-red', 'stops_on_yellow': 'yellow-stop'}[suffix]
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if len(manifest['cases']) not in (1, 2, 3, 4) or manifest['cases'][0]['case_id'] != HERE.name + '__entry_before_red':
        raise ValueError('Unexpected existing exact-case manifest; preserve prior work')
    construction = deepcopy(json.loads((HERE / 'construction.json').read_text()))
    construction['case_id'] = case
    construction['measurement_plan']['saved_processing_status'] = 'pending_exact_case_proof'
    for entry in construction['files']:
        if entry['path'] == 'config.json':
            config = json.loads(entry['content'])
            config['selected_case_id'] = case
            config['case']['case_id'] = case
            entry['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
            break
    else:
        raise ValueError('First construction did not include inline configuration')
    if suffix == 'stops_on_yellow':
        for entry in construction['files']:
            if entry['path'] == 'yellow_red_finalizer.py':
                old = "            'target_matched': matched,\n"
                new = ("            'no_body_entry': {'value': measure_no_entry(report),\n"
                       "                              'method': 'measure_no_entry',\n"
                       "                              'sources': report['sources']},\n" + old)
                if entry['content'].count(old) != 1:
                    raise ValueError('Unexpected inline finalizer source')
                entry['content'] = entry['content'].replace(old, new)
                break
        else:
            raise ValueError('Missing inline finalizer')
    write(HERE / rel, construction)
    contract = deepcopy(json.loads((HERE / 'measurement-contract.json').read_text()))
    contract['case_id'] = case
    if suffix == 'stops_on_yellow':
        dispositions = json.loads((HERE / 'case-plan.json').read_text())['requirement_dispositions']
        contract['requirements'] = [item for item in contract['requirements'] if item['disposition_index'] != 1]
        contract['requirements'].append({
            'disposition_index': 4, 'requirement': dispositions[4]['requirement'],
            'source': dispositions[4]['source'], 'output_key': 'no_body_entry',
            'method': 'measure_no_entry', 'value_type': 'boolean', 'kind': 'measured',
            'inputs': ['signal_vehicle_history.jsonl', 'video_frames.jsonl', 'junction_context.json']})
    write(HERE / contract_path, contract)
    first = manifest['cases'][0]
    second = {
        'case_id': case, 'kind': 'delivery', 'construction': str(rel),
        'construction_sha256': sha(HERE / rel),
        'candidate_risk': deepcopy(first['candidate_risk']), 'candidates': [],
        'measurement_contract': str(contract_path),
        'measurement_procedure': deepcopy(first['measurement_procedure']),
        'native_handoff': deepcopy(first['native_handoff']),
        'acquisition': deepcopy(first['acquisition']),
    }
    recipe = HERE / (stem + '-fixture-recipe.json')
    if recipe.is_file():
        second['fixture_recipe'] = 'work/' + HERE.name + '/' + recipe.name
    offline_log = HERE / (stem + '-offline.log')
    if offline_log.is_file():
        second['offline'] = {
            'command': ('.venv-cpu/bin/python runtime.py offline --manifest work/' +
                        HERE.name + '/execution-manifest.json --case ' + case +
                        ' --output .runtime-work/c158196-yellow-red-' + stem + '-offline'),
            'construction_sha256': sha(HERE / rel), 'exit_code': 0,
            'log': offline_log.name, 'log_sha256': sha(offline_log)}
    compatibility = HERE / (stem + '-compatibility.json')
    if compatibility.is_file():
        second['compatibility'] = {
            'receipt': compatibility.name, 'sha256': sha(compatibility),
            'log': stem + '-compatibility-analysis.log',
            'replay_command': ('.venv-cpu/bin/python runtime.py compatibility --manifest work/' +
                               HERE.name + '/execution-manifest.json --case ' + case +
                               ' --output .runtime-work/c158196-yellow-red-' + stem + '-compatibility' +
                               ' --library runtime/library --validator ' +
                               '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')}
        second['negative'] = {'log': stem + '-negative-analysis.log'}
    match = next((i for i, entry in enumerate(manifest['cases']) if entry['case_id'] == case), None)
    if match is None:
        manifest['cases'].append(second)
    else:
        for key in second:
            manifest['cases'][match][key] = second[key]
    write(manifest_path, manifest)
    print(json.dumps({'case_id': case, 'construction_sha256': sha(HERE / rel),
                      'manifest_sha256': sha(manifest_path), 'status': 'draft'}))


if __name__ == '__main__':
    main()
