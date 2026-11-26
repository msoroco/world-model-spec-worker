"""Bind two exact school-zone drafts to pinned public CPU diagnostics."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    draft = json.loads((ROOT / 'draft-native-manifest.json').read_text())
    cases = []
    proposals = []
    for entry in draft['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        construction = json.loads((ROOT / entry['construction']).read_text())
        entry['measurement_contract'] = 'measurement-contract.json'
        entry['fixture_recipe'] = str((ROOT / ('diagnostic-recipe-' + suffix + '.json')).relative_to(REPO))
        entry['measurement_procedure'] = {'entrypoint': 'finalize.py'}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            channel['name']: {'entrypoint': 'runner.py',
                              'method': channel['method'],
                              'evidence': ['native-motion.jsonl', 'school-context.json']}
            for channel in construction['recording_description']['channels']}
        cases.append(entry)
        proposals.append({'case_id': case_id, 'target_law_id': 'NRS-484B-363-3',
                          'target_type': 'delivery',
                          'rationale': 'Exercise original school-zone U-turn source branch',
                          'variable_assignments': {
                              'u_turn_request': {'kind': 'subject_behavior',
                                                 'value': suffix == 'controlled_2'}},
                          'unresolved_judgment_calls': [
                              'official zone designation', 'child presence',
                              'school session and operation', 'beacon and sign state',
                              'each statutory exception applicability'],
                          'recording_description': construction['recording_description']})
    if not (ROOT / 'proposals/semantic-index.json').is_file():
        write(ROOT / 'proposals/cases.json', {'cell_id': 'C263073',
            'actor': 'motor_vehicle_driver', 'status': 'partial',
            'sweep_specs': [], 'sweeps_expanded': True, 'cases': proposals})
    write(ROOT / 'draft-execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'partial', 'cases': cases})
    print('draft-cases', len(cases))


if __name__ == '__main__':
    main()
