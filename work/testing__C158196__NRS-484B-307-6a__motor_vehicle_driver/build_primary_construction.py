"""Bind the exact first selected yellow/red construction for CPU offline checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + '__entry_before_red'
FILES = ('runner.py', 'signal_control.py', 'yellow_red_capture.py',
         'yellow_red_policy.py', 'red_entry_measurements.py', 'yellow_red_finalizer.py',
         'validate_signal_site.py', 'yellow-red-site.xodr', 'config.json',
         'tests/test_native_capture_draft.py', 'tests/test_red_entry.py',
         'tests/test_yellow_red_policy.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    config = json.loads((HERE / 'config.json').read_text())
    if config['selected_case_id'] != CASE:
        raise ValueError('Root configuration selects another exact case')
    construction = {
        'case_id': CASE, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
        'actor': config['actor'], 'entrypoint': 'runner.py', 'status': 'draft',
        'recording_description': config['recording_description'],
        'measurement_plan': {
            'raw_sources': ['junction_context.json', 'signal_vehicle_history.jsonl',
                            'video_frames.jsonl', 'overview.mkv', 'approach.mkv',
                            'reference_corner.mkv', 'driver_reference.mkv'],
            'analysis_entrypoint': 'yellow_red_finalizer.py',
            'saved_processing_status': 'diagnostic_source_proof_passed'},
        'files': [{'path': name, 'content': (HERE / name).read_text()} for name in FILES],
        'static_checks': [
            'Validate authored OpenDRIVE head validity and controller linkage',
            'Select one live Native head by affected ego lane',
            'Check exact case, 20 Hz, 900 frames, four camera mounts and source context',
            'Retain same-tick Native body, signal, camera and frame-map sources'],
        'termination_rules': [
            'Capture exactly 900 original frames or fail the attempt',
            'Restore the prior world after capture or failure',
            'Seal capture only after encoder closure and restoration'],
        'mechanisms': [
            'Generate the owned OpenDRIVE signalized site',
            'Apply Green/Yellow/Red frame policy using observed ego distance and speed',
            'Retain four synchronized FFV1 original camera streams and source histories']}
    construction_path = HERE / 'construction.json'
    write(construction_path, construction)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': '5b4738624542c97f321a302bd49b9ec154cb2cf63778acf64ba6042f8d5b4fd3',
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': 'construction.json',
                           'construction_sha256': sha(construction_path),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Native head may not govern ego lane or remain visible in original forward cameras; timing policy may miss body entry.'},
                           'candidates': [],
                           'measurement_contract': 'measurement-contract.json',
                           'fixture_recipe': 'work/' + ASSIGNMENT + '/primary-fixture-recipe.json',
                           'measurement_procedure': {'entrypoint': 'yellow_red_finalizer.py'},
                           'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                              'host_env_var': 'CARLA_HOST',
                                              'port_env_var': 'CARLA_PORT'}}]}
    offline_log = HERE / 'primary-offline-v5.log'
    if offline_log.is_file():
        manifest['cases'][0]['offline'] = {
            'command': ('.venv-cpu/bin/python runtime.py offline --manifest work/' +
                        ASSIGNMENT + '/execution-manifest.json --case ' + CASE +
                        ' --output .runtime-work/c158196-yellow-red-primary-offline-v5'),
            'construction_sha256': sha(construction_path), 'exit_code': 0,
            'log': 'primary-offline-v5.log', 'log_sha256': sha(offline_log)}
    compatibility = HERE / 'primary-compatibility.json'
    if compatibility.is_file():
        entry = manifest['cases'][0]
        entry['compatibility'] = {
            'receipt': 'primary-compatibility.json', 'sha256': sha(compatibility),
            'log': 'primary-compatibility-analysis.log',
            'replay_command': ('.venv-cpu/bin/python runtime.py compatibility --manifest work/' +
                               ASSIGNMENT + '/execution-manifest.json --case ' + CASE +
                               ' --output .runtime-work/c158196-yellow-red-compatibility-v2' +
                               ' --library runtime/library --validator ' +
                               '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')}
        entry['negative'] = {'log': 'primary-negative-analysis.log'}
        entry['acquisition'] = {
            name: {'entrypoint': 'yellow_red_finalizer.py',
                   'method': method, 'evidence': evidence}
            for name, method, evidence in (
                ('signal_state', 'original same-frame Native signal readback',
                 ['signal_vehicle_history.jsonl', 'video_frames.jsonl']),
                ('ego_body_vertices_xy_m', 'original complete body vertices',
                 ['signal_vehicle_history.jsonl', 'junction_context.json']),
                ('ego_body_in_intersection', 'saved body-polygon intersection overlap',
                 ['signal_vehicle_history.jsonl', 'junction_context.json']),
                ('ego_approach_speed', 'original same-frame ego speed readback',
                 ['signal_vehicle_history.jsonl', 'video_frames.jsonl']),
                ('junction_signal_context', 'saved governing head and lane context join',
                 ['junction_context.json', 'signal_vehicle_history.jsonl']))}
    previous_path = HERE / 'execution-manifest.json'
    if previous_path.is_file():
        previous = json.loads(previous_path.read_text())
        if previous.get('assignment_id') == ASSIGNMENT:
            manifest['cases'].extend(case for case in previous.get('cases', [])
                                     if case.get('case_id') != CASE)
    write(previous_path, manifest)
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(construction_path),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'status': 'draft'}))


if __name__ == '__main__':
    main()
