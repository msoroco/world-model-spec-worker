"""Bind selected signal-approach cases and source-specific measurement contracts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
AID = ROOT.name
SOURCES = ['signal_raw.json', 'context-survey.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr']
OUTPUT_KEYS = ['stopping_context', 'signal_approach_distance', 'official_signal_context']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    offline = json.loads((ROOT/'native/selected-offline-manifest.json').read_text())
    proposals = {'format': 'canonical-cases', 'status': 'draft',
                 'cell_id': 'C229987', 'actor': 'motor_vehicle_driver',
                 'sweep_specs': [], 'cases': []}
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                'status': 'draft', 'cases': []}
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        entry = next(e for e in offline['cases'] if e['case_id'] == case_id)
        construction_path = ROOT/'native'/entry['construction']
        construction = json.loads(construction_path.read_text())
        proposals['cases'].append({
            'case_id': case_id, 'target_law_id': plan['law_id'],
            'target_type': 'controlled_attempt', 'rationale': case['selection_reason'],
            'variable_assignments': {'requested_front_gap_ft': case['requested_setting']},
            'unresolved_judgment_calls': [
                'Official signal and highway status need original source review',
                'Stop/stand/park classification and each statutory exception need original review',
                'Actual footprint, camera pixels and physical stop need Native review'],
            'recording_description': construction['recording_description']})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'status': 'draft',
                    'negative': {'remove': ['signal_raw.json'],
                                 'error_contains': 'Missing required source: signal_raw.json'},
                    'requirements': []}
        for index, disposition in enumerate(plan['requirement_dispositions']):
            contract['requirements'].append({
                'disposition_index': index, 'requirement': disposition['requirement'],
                'source': disposition['source'], 'inputs': SOURCES,
                'kind': 'measured' if index == 1 else 'sourced_context',
                'method': 'measure_signal_approach',
                'output_key': OUTPUT_KEYS[index], 'value_type': 'object'})
        contract_path = ROOT/'native'/f'{suffix}-measurement-contract.json'
        write(contract_path, contract)
        log = ROOT/'native'/f'{suffix}-offline.log'
        manifest['cases'].append({
            'id': suffix, 'case_id': case_id, 'kind': 'delivery',
            'construction': str(construction_path.relative_to(ROOT)),
            'construction_sha256': sha(construction_path),
            'measurement_contract': str(contract_path.relative_to(ROOT)),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': str((ROOT/'native/diagnostic'/suffix/'fixture-recipe.json').relative_to(REPO)),
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'recording_description': construction['recording_description'],
            'candidate_risk': entry['candidate_risk'], 'candidates': [],
            'offline': {'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{AID}/execution-manifest.json --case {case_id} --output .runtime-work/c229987/offline-{suffix}',
                        'exit_code': 0, 'construction_sha256': sha(construction_path),
                        'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}})
    write(ROOT/'proposals/cases.json', proposals)
    write(ROOT/'execution-manifest.json', manifest)
    print(json.dumps({'cases': [e['case_id'] for e in manifest['cases']]}))


if __name__ == '__main__':
    main()
