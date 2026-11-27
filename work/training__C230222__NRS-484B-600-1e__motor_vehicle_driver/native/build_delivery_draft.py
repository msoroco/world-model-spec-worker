"""Bind exact constructions, source fixtures, and requirement measurements."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SOURCE_FILES = ['native_motion.jsonl', 'road_context.json', 'video_frames.jsonl',
                'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    offline_manifest = json.loads((ROOT/'native/selected-offline-manifest.json').read_text())
    proposals = {'format': 'canonical-cases', 'status': 'draft', 'cell_id': 'C230222',
                 'actor': 'motor_vehicle_driver', 'sweep_specs': [], 'cases': []}
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                'status': 'draft', 'cases': []}
    for index, case in enumerate(plan['cases']):
        case_id = case['case_id']
        probe = case_id.rsplit('__', 1)[-1]
        offline = next(row for row in offline_manifest['cases'] if row['case_id'] == case_id)
        construction_path = ROOT/'native'/offline['construction']
        construction = json.loads(construction_path.read_text())
        proposal = {'case_id': case_id, 'target_law_id': plan['law_id'],
                    'target_type': 'controlled_attempt', 'rationale': case['selection_reason'],
                    'variable_assignments': {'requested_speed_mph': [78, 80, 82][index]},
                    'unresolved_judgment_calls': ['Actual measured speed and physical camera coverage require Native review'],
                    'recording_description': construction['recording_description']}
        proposals['cases'].append(proposal)
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'status': 'draft', 'negative': {'remove': ['native_motion.jsonl'],
                                                   'error_contains': 'Missing required source: native_motion.jsonl'},
                    'requirements': []}
        for disposition_index, disposition in enumerate(plan['requirement_dispositions']):
            contract['requirements'].append({
                'disposition_index': disposition_index,
                'requirement': disposition['requirement'], 'source': disposition['source'],
                'inputs': SOURCE_FILES, 'kind': 'measured' if disposition_index else 'sourced_context',
                'method': 'measure_speed',
                'output_key': ['subject_context', 'speed_observation', 'unconditional_speed_context', 'speed_boundary_context'][disposition_index],
                'value_type': 'object'})
        contract_path = ROOT/'native'/f'{probe}-measurement-contract.json'
        write(contract_path, contract)
        log = ROOT/'native'/f'{probe}-offline.log'
        manifest['cases'].append({
            'id': probe, 'case_id': case_id, 'kind': 'delivery', 'construction': str(construction_path.relative_to(ROOT)),
            'construction_sha256': sha(construction_path),
            'measurement_contract': str(contract_path.relative_to(ROOT)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': str((ROOT/'native/diagnostic'/probe/'fixture-recipe.json').relative_to(REPO)),
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'recording_description': construction['recording_description'],
            'candidate_risk': offline['candidate_risk'], 'candidates': [],
            'offline': {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/'+ASSIGNMENT+
                                   '/execution-manifest.json --case '+case_id+' --output .runtime-work/c230222-offline-'+probe,
                        'exit_code': 0, 'construction_sha256': sha(construction_path),
                        'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}})
    write(ROOT/'proposals/cases.json', proposals)
    write(ROOT/'execution-manifest.json', manifest)
    print(json.dumps({'cases': [row['case_id'] for row in manifest['cases']],
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
