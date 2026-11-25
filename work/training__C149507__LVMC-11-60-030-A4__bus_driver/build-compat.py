"""Bind selected bus measurement contracts and public diagnostic recipes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SOURCES = ['video_frames.jsonl', 'bus-traffic-poses.jsonl',
           'bus-zone-review.json', 'road.xodr', 'curb-calibration.json',
           'bus-classification.json', 'wheel-geometry.json',
           'loading-location.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest = json.loads((HERE / 'selected-offline-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proposal_cases = []
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.rsplit('__', 1)[-1]
        contract = {'format': 'worker-measurement-contract', 'case_id': cid,
            'requirements': [{'disposition_index': 0,
                'requirement': plan['requirement_dispositions'][0]['requirement'],
                'source': plan['requirement_dispositions'][0]['source'],
                'output_key': 'bus_loading_measurement',
                'method': 'reviewed_measure', 'value_type': 'object',
                'kind': 'measured', 'inputs': SOURCES}],
            'negative': {'remove': ['bus-zone-review.json'],
                'error_contains': 'Missing required source: bus-zone-review.json'}}
        write(HERE / 'cases' / suffix / 'measurement-contract.json', contract)
        entry.pop('preparation_status', None)
        entry['measurement_contract'] = f'cases/{suffix}/measurement-contract.json'
        entry['measurement_procedure'] = {'entrypoint': 'finalize_bus.py',
            'output_schema': 'worker-analysis-report-v1'}
        entry['fixture_recipe'] = f'work/{AID}/cases/{suffix}/recipe.json'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        proposal_cases.append({'case_id': cid, 'target_law_id': config['law_id'],
            'target_type': 'controlled_attempt', 'rationale':
                'Source-measured bus wheel gap at stopped loading; no legal verdict',
            'variable_assignments': {'front_wheel_curb_gap_request_m':
                {'kind': 'controller', 'value': {'probe_1': .30, 'probe_2': .70, 'probe_3': .4572}[suffix]},
                'bus_stop_and_other_traffic': {'kind': 'world_setup', 'value': True},
                'observed_wheel_gap_m': {'kind': 'subject_behavior', 'value': None}},
            'unresolved_judgment_calls':
                ['Approximately parallel and undue impedance need independent review'],
            'recording_description': config['recording_description']})
    write(HERE / 'proposals' / 'cases.json', {'cell_id': 'C149507',
        'actor': 'bus_driver', 'status': 'draft', 'sweeps_expanded': True,
        'cases': proposal_cases})
    manifest['status'] = 'draft'
    manifest['delivery_ready'] = False
    manifest['runtime_manifest_sha256'] = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    write(HERE / 'compat-draft-manifest.json', manifest)
    print([e['case_id'] for e in manifest['cases']])


if __name__ == '__main__':
    main()
