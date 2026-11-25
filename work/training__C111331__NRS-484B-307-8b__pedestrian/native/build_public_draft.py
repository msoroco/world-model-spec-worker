"""Bind exact Native drafts to measurement and public compatibility inputs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    draft = json.loads((HERE / 'draft-native-execution-manifest.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    contract_rows = [
        ('steady_red_source', 'measure_red_signal',
         ['red-entry-original.jsonl', 'video_frames.jsonl']),
        ('entry_and_other_device_source', 'measure_entry',
         ['red-entry-original.jsonl', 'camera-sources.jsonl']),
        ('intersection_entry_scope', 'measure_scope',
         ['red-entry-original.jsonl', 'capture/evidence.jsonl'])]
    cases = []
    proposals = []
    for entry in draft['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        construction = FOLDER / 'native' / entry['construction']
        source = json.loads(construction.read_text())
        contract = {'format': 'worker-measurement-contract',
                    'requirements': [{'disposition_index': i,
                                      'requirement': row['requirement'],
                                      'source': row['source'],
                                      'output_key': key, 'method': method,
                                      'kind': 'measured' if i < 2 else 'sourced_context',
                                      'value_type': 'object', 'inputs': inputs}
                                     for i, ((key, method, inputs), row)
                                     in enumerate(zip(contract_rows, plan['requirement_dispositions']))],
                    'negative': {'remove': ['red-entry-original.jsonl'],
                                 'error_contains': 'Missing required source: red-entry-original.jsonl'}}
        contract_path = FOLDER / ('measurement-' + condition + '.json')
        write(contract_path, contract)
        acquisition = {name: {'entrypoint': 'runner.py' if name in
                             ('camera_frame_join', 'kin.position', 'kin.heading') else 'finalize.py',
                             'method': 'original 600-frame Native source and saved join',
                             'evidence': 'Synthetic diagnostic only; original physical review pending'}
                       for name in [*json.loads(next(f['content'] for f in source['files']
                                                      if f['path'] == 'config.json'))['required_atoms'],
                                    'dev.pedestrian_signal', 'camera_frame_join']}
        offline_log = FOLDER / ('native-red-offline-' + condition + '-primary.log')
        cases.append({**entry, 'construction': 'native/' + entry['construction'],
                      'candidates': [{**candidate,
                                      'construction': 'native/' + candidate['construction']}
                                     for candidate in entry['candidates']],
                      'kind': 'delivery', 'id': 'primary',
                      'measurement_contract': contract_path.name,
                      'measurement_procedure': {'entrypoint': 'finalize.py',
                                                'output_schema': 'c111331-red-entry-saved-analysis-v1'},
                      'fixture_recipe': str((FOLDER / ('diagnostic-' + condition + '-recipe.json')).relative_to(REPO)),
                      'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                         'host_env_var': 'CARLA_HOST',
                                         'port_env_var': 'CARLA_PORT'},
                      'acquisition': acquisition,
                      'offline': {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                                  + str((HERE / 'draft-native-execution-manifest.json').relative_to(REPO))
                                  + ' --case ' + entry['case_id'] + ' --candidate primary --output .runtime-work/c111331-finalizer/offline-'
                                  + condition + '-primary',
                                  'exit_code': 0,
                                  'construction_sha256': entry['construction_sha256'],
                                  'log': offline_log.name, 'log_sha256': sha(offline_log)}})
        proposals.append({'case_id': entry['case_id'],
                          'target_type': 'planned_delivery_comparison',
                          'recording_description': source['recording_description']})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': FOLDER.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'public_compatibility_draft', 'cases': cases}
    write(FOLDER / 'execution-manifest.json', manifest)
    write(FOLDER / 'proposals/cases.json', {'cases': proposals})
    print(json.dumps({'cases': len(cases),
                      'manifest_sha256': sha(FOLDER / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
