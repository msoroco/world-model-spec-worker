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
            offline_output = 'offline-' + suffix
            entry['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + aid +
                           '/execution-manifest.json --case ' + case_id +
                           ' --output .runtime-work/c111301-refresh/' + offline_output +
                           ' --python $PWD/.venv-cpu/bin/python',
                'construction_sha256': entry['construction_sha256'],
                'exit_code': 0, 'log': str(offline.relative_to(HERE)),
                'log_sha256': sha(offline)}
        saved = case_folder / 'processing.json'
        saved_log = case_folder / 'cpu-saved.log'
        if saved.is_file() and saved_log.is_file() and json.loads(saved.read_text()).get('native_revision', {}).get('construction_sha256') == entry['construction_sha256']:
            command = '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + aid + '/execution-manifest.json --case ' + case_id + ' --attempt .runtime-work/c111301-refresh/saved-' + suffix + '-attempt --output .runtime-work/c111301-refresh/saved-' + suffix + '-output --library runtime/library --validator .runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck'
            entry['post_capture'] = {
                'command': command, 'feedback_command': command + ' ; inspect feedback.json',
                'recorded_only': True, 'originals_preserved': True,
                'synthetic_fixture': True, 'test_exit_code': 0,
                'test_log': str(saved_log.relative_to(HERE)), 'test_log_sha256': sha(saved_log),
                'processing_receipt_sha256': sha(saved)}
        delivery_log = case_folder / 'cpu-independent-delivery.log'
        negative_log = case_folder / 'cpu-independent-negative.log'
        if delivery_log.is_file() and negative_log.is_file():
            command = '.venv-cpu/bin/python work/' + aid + '/independent_delivery_cpu.py --attempt .runtime-work/c111301-refresh/saved-' + suffix + '-attempt --case ' + case_id + ' --scratch .runtime-work/c111301-refresh/delivery-' + suffix + '-positive --output .runtime-work/c111301-refresh/delivery-' + suffix + '-positive.json'
            negative_command = '.venv-cpu/bin/python work/' + aid + '/independent_delivery_cpu.py --attempt .runtime-work/c111301-refresh/saved-' + suffix + '-attempt --case ' + case_id + ' --scratch .runtime-work/c111301-refresh/delivery-' + suffix + '-negative --output .runtime-work/c111301-refresh/delivery-' + suffix + '-negative.json --negative'
            entry['delivery_acceptance'] = {
                'case_id': case_id, 'sets': ['full-test'],
                'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
                'scope': 'synthetic diagnostic component check; original physical completion unverified',
                'command': command, 'negative_command': negative_command,
                'script': 'independent_delivery_cpu.py', 'script_sha256': sha(HERE / 'independent_delivery_cpu.py'),
                'test_exit_code': 0, 'test_log': str(delivery_log.relative_to(HERE)), 'test_log_sha256': sha(delivery_log),
                'negative_exit_code': 1, 'negative_expected_error': 'original source changed: approach.mkv',
                'negative_log': str(negative_log.relative_to(HERE)), 'negative_log_sha256': sha(negative_log)}
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': aid,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return [entry['case_id'] for entry in cases]


if __name__ == '__main__':
    print(json.dumps(build()))
