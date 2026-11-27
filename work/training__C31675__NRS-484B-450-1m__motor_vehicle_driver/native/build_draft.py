"""Bind exact bridge-halt pair to source-hashed, offline-testable Native bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
AID = ASSIGNMENT.name
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
CHANNELS = ('bridge_relation', 'speed_mps', 'stationary_candidate',
            'halt_purpose_context', 'traffic_conflict_context',
            'law_compliance_context', 'police_direction_context',
            'device_direction_context', 'source_camera_frame_join')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for suffix in ('false', 'true'):
        case_id = AID + '__' + suffix
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [
                {'disposition_index': 0, 'requirement': 'text-0',
                 'source': 'inputs/coverage/branch-sources.json',
                 'output_key': 'exception_context', 'method': 'exception_observation',
                 'value_type': 'object', 'kind': 'sourced_context',
                 'inputs': ['bridge-trace.jsonl', 'road.xodr']},
                {'disposition_index': 1, 'requirement': 'text-1',
                 'source': 'inputs/coverage/branch-sources.json',
                 'output_key': 'bridge_place', 'method': 'place_observation',
                 'value_type': 'object', 'kind': 'measured',
                 'inputs': ['bridge-map.json', 'bridge-trace.jsonl',
                            'video_frames.jsonl']},
                {'disposition_index': 2, 'requirement': 'reviewed-scope-0',
                 'source': 'inputs/coverage/branch-sources.json',
                 'output_key': 'bridge_scope', 'method': 'bridge_scope_observation',
                 'value_type': 'object', 'kind': 'measured',
                 'inputs': ['bridge-map.json', 'bridge-trace.jsonl']}],
            'negative': {'remove': ['bridge-map.json'],
                         'error_contains': 'Missing required source: bridge-map.json'}}
        contract_path = ASSIGNMENT / 'cases' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        description = {'channels': [{'name': name, 'unit': 'structured',
            'sampling_rate_hz': 20, 'method': 'Native source-bound bridge/body, camera and exception review',
            'time_window': '600 original frames', 'reference_frame': 'Native frame and surveyed bridge deck',
            'uncertainty': 'physical structure, pixels, halt purpose and legal exception unverified'}
            for name in CHANNELS],
            'context_inputs': [
                {'name': 'Native bridge survey', 'unit': 'structured',
                 'method': 'Original road elevation and bridge polygon survey'},
                {'name': 'original actor traces', 'unit': 'structured',
                 'method': 'Original Native actor transforms and velocities'},
                {'name': 'traffic and authority review', 'unit': 'structured',
                 'method': 'Original source review for traffic, law, police and device context'}],
            'limitations': ['No synthetic fixture establishes physical bridge support, actual halt cause or legal outcome']}
        configs = {}
        for candidate, start_x in (('primary', -75.0), ('fallback1', -85.0)):
            config = {'case_id': case_id, 'selected_case_id': case_id,
                'supported_case_ids': [AID + '__false', AID + '__true'],
                'candidate_id': candidate, 'initial_spawn_x_m': start_x,
                'law_id': 'NRS-484B-450-1m', 'cell_id': 'C31675',
                'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
                'physical_completion': {'criterion': 'travel_progress',
                                        'minimum_progress_m': 20,
                                        'completion_goal_method': 'Observed route progress before an independently reviewed stationary interval; engineering fixture only'},
                'required_atoms': [], 'source_packets': [],
                'cameras': [{'name': name, 'width': width, 'height': height,
                             'fov_deg': 85, 'pose_strategy': 'fixed surveyed bridge view'}
                            for name, width, height in CAMERAS],
                'case': {'case_id': case_id, 'recording_description': description},
                'recording_description': description,
                'requested_stationary_footprint_on_bridge': suffix == 'true',
                'requested_halt_cause': 'voluntary_destination'}
            construction = {'case_id': case_id, 'law_id': 'NRS-484B-450-1m',
                'cell_id': 'C31675', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'recording_description': description,
                'measurement_plan': {'entrypoint': 'finalize.py',
                    'required_sources': ['bridge-trace.jsonl', 'bridge-map.json',
                                         'video_frames.jsonl'],
                    'status': 'source_bound_cpu_draft'},
                'files': []}
            for name in ('runner.py', 'controller.py', 'geometry.py',
                         'finalize.py', 'comparison_audit.py', 'tests/test_native.py',
                         'tests/test_finalize.py'):
                construction['files'].append({'path': name,
                    'content': (HERE / name).read_text()})
            construction['files'].append({'path': 'bridge_measure.py',
                'content': (ASSIGNMENT / 'bridge_measure.py').read_text()})
            construction['files'].append({'path': 'config.json',
                'content': json.dumps(config, indent=2, sort_keys=True) + '\n'})
            path = ASSIGNMENT / 'cases' / suffix / candidate / 'construction.json'
            write(path, construction)
            configs[candidate] = (path.relative_to(ASSIGNMENT).as_posix(), sha(path))
        entry = {'case_id': case_id, 'construction': configs['primary'][0],
                 'construction_sha256': configs['primary'][1],
                 'measurement_contract': str(contract_path.relative_to(ASSIGNMENT)),
                 'measurement_procedure': {'entrypoint': 'finalize.py'},
                 'candidate_risk': {'status': 'physical',
                   'reason': 'Native halt may overshoot authored bridge or ground destination on elevated approach'},
                 'candidates': [{'id': 'fallback1', 'construction': configs['fallback1'][0],
                   'construction_sha256': configs['fallback1'][1],
                   'trigger': {'source': 'bridge-trace.jsonl', 'metric': 'observed halt position',
                     'failure_condition': 'ego still moving or body outside requested destination after braking'},
                   'changed_knobs': ['initial_spawn_x_m: -75 to -85 m']}],
                 'draft_status': 'offline_construction_only'}
        entries.append(entry)
    write(ASSIGNMENT / 'draft-execution-manifest.json',
          {'format': 'c31675-bridge-draft-v1', 'cases': entries,
           'runtime_manifest_sha256': '5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3',
           'physical_legal_acceptance_claimed': False})
    print(json.dumps({'cases': [e['case_id'] for e in entries],
                      'candidates_per_case': 2, 'status': 'draft'}))


if __name__ == '__main__':
    build()
