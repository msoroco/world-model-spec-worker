"""Bind exact NRS one-way parking drafts to selected delivery measurements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('witness_1', True), ('witness_2', False),
         ('exception_1_1', False), ('exception_1_2', True))
BASE_SOURCES = ['road.xodr', 'road-context.json', 'road-review.json',
                'vehicle-pose.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                'capture/evidence.jsonl', 'source_context/one_way_designation.txt',
                'source_context/street_boundary.txt', 'source_context/device_inventory.txt']
EXTRA_SOURCES = ['source_context/' + name + '.txt' for name in
                 ('device_authority', 'device_content', 'device_erection', 'device_governance')]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'selected_cpu_proofs_in_progress', 'delivery_ready': False,
                'original_native_observed': False, 'cases': []}
    for number, (suffix, permission) in enumerate(CASES, 1):
        case_id = ASSIGNMENT + '__' + suffix
        draft = json.loads((HERE / 'draft-permission' / suffix / 'primary/construction.json').read_text())
        construction = ('construction.json' if number == 1 else
                        'cases/' + suffix + '/construction.json')
        write(construction, draft)
        if number == 1:
            for item in draft['files']:
                path = HERE / item['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(item['content'])
        sources = BASE_SOURCES + (EXTRA_SOURCES if permission else [])
        contract = 'cases/' + suffix + '/measurement-contract.json'
        write(contract, {'format': 'worker-measurement-contract', 'case_id': case_id,
                         'requirements': [{
                             'disposition_index': i, 'requirement': disposition['requirement'],
                             'source': disposition['source'], 'kind': 'measured',
                             'method': 'measure_one_way_parking', 'output_key': 'one_way_parking',
                             'value_type': 'object', 'inputs': sources}
                             for i, disposition in enumerate(plan['requirement_dispositions'])
                             if disposition['status'] == 'selected_required' and
                             case_id in disposition['case_ids']],
                         'negative': {'remove': ['source_context/device_inventory.txt'],
                                      'error_contains': 'Missing required source: source_context/device_inventory.txt'}})
        offline = {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ASSIGNMENT +
                   '/selected-parking-manifest.json --case ' + case_id +
                   ' --candidate primary --output .runtime-work/nrs497-offline-' + suffix,
                   'exit_code': 0, 'construction_sha256': sha(HERE / construction),
                   'log': 'proofs/offline-' + suffix + '.log'}
        manifest['cases'].append({'case_id': case_id, 'id': 'primary', 'kind': 'delivery',
            'construction': construction, 'construction_sha256': sha(HERE / construction),
            'offline': offline,
            'candidate_risk': {'status': 'physical',
                               'reason': 'Actual left-curb stopping motion and permission sign pixels require Native review'},
            'candidates': [], 'measurement_contract': contract,
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': 'work/' + ASSIGNMENT + '/cases/' + suffix + '/fixture-recipe.json',
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}})
    write('selected-parking-manifest.json', manifest)
    write('execution-manifest.json', manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'construction_hashes': [entry['construction_sha256'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
