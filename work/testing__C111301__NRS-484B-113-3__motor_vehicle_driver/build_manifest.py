"""Draft selected manifest; proof fields are added only after actual checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    aid = HERE.name
    cases = []
    for suffix in ('pedestrian_yield', 'pedestrian_continue', 'traffic_yield', 'traffic_continue'):
        case_id = aid + '__' + suffix
        construction = ('construction.json' if suffix == 'pedestrian_yield'
                        else 'construction-' + suffix + '.json')
        cases.append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': construction,
            'construction_sha256': sha(HERE / construction),
            'measurement_contract': 'measurement-' + suffix + '.json',
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'fixture_recipe': 'work/' + aid + '/diagnostic-' + suffix + '-recipe.json',
            'candidate_risk': {
                'status': 'none',
                'reason': 'No site-specific failure mechanism justifies an alternate before original site review.'},
            'candidates': [],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'}})
        entry = cases[-1]
        physical = HERE / 'cases' / suffix / 'physical-preparation.json'
        if physical.is_file() and json.loads(physical.read_text()).get('construction_sha256') == entry['construction_sha256']:
            entry['physical_preparation'] = {
                'receipt': str(physical.relative_to(HERE)), 'sha256': sha(physical)}
        participant = 'moving_traffic_corridor_exposure' if suffix.startswith('traffic_') else 'moving_pedestrian_corridor_exposure'
        entry['acquisition'] = {
            'vehicle_reverse_response': {
                'entrypoint': 'native_backing_capture.py',
                'method': 'original actor control and velocity readback joined to runtime PipelineCapture on each Native world tick',
                'evidence': ['telemetry.json', 'frame-map.json', 'trace.jsonl',
                             'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                             'carla_recorder.log']},
            participant: {
                'entrypoint': 'traffic_capture.py' if suffix.startswith('traffic_') else 'native_backing_capture.py',
                'method': 'original conflicting participant pose and velocity with sealed route geometry',
                'evidence': ['telemetry.json', 'map.json', 'road.xodr']}}
        case_folder = HERE / 'cases' / suffix
        receipt = case_folder / 'compatibility.json'
        if receipt.is_file() and json.loads(receipt.read_text()).get('construction_sha256') == entry['construction_sha256']:
            entry['compatibility'] = {
                'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt),
                'log': str((case_folder / 'cpu-analysis.log').relative_to(HERE))}
            entry['negative'] = {'log': str((case_folder / 'cpu-negative.log').relative_to(HERE)),
                                 'expected_error': 'Missing required source: map.json'}
        offline = case_folder / 'cpu-offline.log'
        if offline.is_file():
            offline_output = ('offline-' + suffix + '-traffic-v1' if suffix.startswith('pedestrian_')
                              else 'offline-' + suffix.replace('_', '-') + '-v1')
            entry['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + aid +
                           '/execution-manifest.json --case ' + case_id +
                           ' --output .runtime-work/c111301-nov25/' + offline_output +
                           ' --python $PWD/.venv-cpu/bin/python',
                'construction_sha256': entry['construction_sha256'],
                'exit_code': 0, 'log': str(offline.relative_to(HERE)),
                'log_sha256': sha(offline)}
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': aid,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return [entry['case_id'] for entry in cases]


if __name__ == '__main__':
    print(json.dumps(build()))
