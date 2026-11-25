"""Bind tested C150129 street constructions into exact selected CPU bundles."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = ('controlled_1', 'controlled_2')
SOURCES = ['vehicle-poses.jsonl', 'parking-inventory.json', 'review.json',
           'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
           'source_context/city_street.txt',
           'source_context/council_designation.txt',
           'source_context/posting_or_marking.txt',
           'source_context/subject_vehicle_status.txt']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = HERE / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'selected_street_cpu_proof_in_progress',
                'delivery_ready': False, 'original_native_observed': False,
                'cases': []}
    proposals = {'cell_id': 'C150129', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
                 'cases': []}
    for suffix in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        draft = json.loads((HERE / 'draft-parking' / suffix / 'primary/construction.json').read_text())
        construction_path = ('construction.json' if suffix == 'controlled_1' else
                             'cases/' + suffix + '/construction.json')
        if suffix == 'controlled_1':
            for item in draft['files']:
                target = HERE / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item['content'])
            description = draft['recording_description']
            proposals['cases'].append({
                'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Unselected neutral definition; no recording or municipal designation asserted.',
                'variable_assignments': {
                    'requested_city_space_occupancy': {'kind': 'controller', 'value': False,
                                                       'unit': 'boolean'},
                    'observed_city_space_occupancy': {'kind': 'subject_behavior',
                                                      'value': None, 'unit': 'boolean'}},
                'recording_description': description,
                'unresolved_judgment_calls': []})
        proposals['cases'].append({
            'case_id': case_id, 'target_law_id': 'LVMC-11-52-340',
            'target_type': ('compliant_attempt' if suffix == 'controlled_1' else
                            'violating_attempt'),
            'rationale': 'Controlled requested parking location; Native occupation and legal status require independent review.',
            'paired_probe_id': ASSIGNMENT + '__comparison',
            'deliberate_differences': ['requested_city_space_occupancy'],
            'probe': {'primary_variable': 'requested_city_space_occupancy',
                      'comparison_or_standard': 'same posted street space and subject with different requested occupation',
                      'target_value_or_branch': suffix},
            'variable_assignments': {
                'requested_city_space_occupancy': {'kind': 'controller',
                                                   'value': suffix == 'controlled_2',
                                                   'unit': 'boolean'},
                'observed_city_space_occupancy': {'kind': 'subject_behavior',
                                                  'value': None, 'unit': 'boolean'}},
            'recording_description': draft['recording_description'],
            'unresolved_judgment_calls': []})
        write(construction_path, draft)
        contract_path = 'cases/' + suffix + '/measurement-contract.json'
        write(contract_path, {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{
                'disposition_index': i,
                'requirement': d['requirement'], 'source': d['source'],
                'kind': 'measured', 'method': 'measure_municipal_street_parking',
                'output_key': 'municipal_street_parking', 'value_type': 'object',
                'inputs': SOURCES,
            } for i, d in enumerate(plan['requirement_dispositions'])
                if d['status'] == 'selected_required' and case_id in d['case_ids']],
            'negative': {'remove': ['source_context/posting_or_marking.txt'],
                         'error_contains': 'Missing required source: source_context/posting_or_marking.txt'},
            'status': 'selected_street_cpu_proof_in_progress',
        })
        number = '1' if suffix == 'controlled_1' else '2'
        log = 'selected-offline-' + number + '.log'
        entry = {'case_id': case_id, 'id': 'primary', 'kind': 'delivery',
                 'construction': construction_path,
                 'construction_sha256': sha(HERE / construction_path),
                 'offline': {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                             'work/' + ASSIGNMENT + '/selected-parking-manifest.json --case ' +
                             case_id + ' --candidate primary --output .runtime-work/c150129/selected-offline-'
                             + number + '-v3',
                             'exit_code': 0, 'construction_sha256': sha(HERE / construction_path),
                             'log': log, 'log_sha256': sha(HERE / log)},
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Actual parking dynamics, sign body placement and pixel legibility require Native review'},
                 'candidates': [], 'measurement_contract': contract_path,
                 'measurement_procedure': {'entrypoint': 'finalize.py'},
                 'fixture_recipe': 'work/' + ASSIGNMENT + '/cases/' + suffix + '/fixture-recipe.json',
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
        manifest['cases'].append(entry)
    write('selected-parking-manifest.json', manifest)
    write('proposals/cases.json', proposals)
    print(json.dumps({'cases': {e['case_id']: e['construction_sha256']
                                for e in manifest['cases']},
                      'manifest': 'selected-parking-manifest.json'}, sort_keys=True))


if __name__ == '__main__':
    main()
