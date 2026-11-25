"""Bind exact current-v2 primary speed construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'slow'), ('probe_2', 'at_default'), ('probe_3', 'fast'))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    proposal_cases = []
    for suffix, speed_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed Native road and original Native frame',
             'uncertainty': '50 ms sampling; street and sign authority unverified',
             'source': 'channels/' + name + '.jsonl'}
            for name, unit, method in (
                ('kin.speed', 'm/s', 'original Native velocity vector magnitude'),
                ('dev.speed_limit_sign', 'structured', 'original sign survey and roadside RGB source'),
                ('dev.governs', 'structured', 'source-hashed sign interval and route position'),
                ('st.roadway', 'structured', 'authored road and Native waypoint readback'),
                ('rel.occupies', 'structured', 'original Native actor position and road waypoint'))],
            'context_inputs': [],
            'limitations': ['Public-street and posted-sign authority need independent original source review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s, _ in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-16-060',
                  'cell_id': 'C179819', 'actor': 'motor_vehicle_driver',
                  'speed_case': speed_case, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                               'height': 1080 if name == 'overview' else 720} for name in CAMERAS],
                  'recording_description': description, 'status': 'cpu_draft_sign_authority_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py',
                              'measure_speed.py', 'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'finalize.py',
                        'required_sources': ['road.xodr', 'sign-survey.json',
                                             'actor-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['800 m paved road', 'Native roadway readback',
                                      '600 frames at 20 Hz', 'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['same roadway and controller; requested speed varies'],
                    'status': 'partial_native_draft_authority_unverified'}
        proposal_cases.append({'case_id': case_id, 'target_law_id': config['law_id'],
            'target_type': {'probe_1': 'below', 'probe_2': 'at', 'probe_3': 'above'}[suffix],
            'rationale': 'Original measured speed at requested setpoint on a reviewed surveyed street',
            'variable_assignments': {'speed_mph': {'kind': 'world_setup',
                'value': {'slow': 20, 'at_default': 25, 'fast': 30}[speed_case]}},
            'unresolved_judgment_calls': ['prima facie legal status', 'posted sign authority'],
            'recording_description': description})
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native speed tracking and public sign governance require original review'},
            'candidates': [], 'measurement_contract': 'draft-exact/' + suffix + '/measurement-contract.json',
            'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostic-' + suffix + '-recipe.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'preparation_status': 'incomplete'})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0, 'requirement': 'LVMC-11-16-060',
                'source': 'LVMC 11.16.060', 'output_key': 'source_bound_speed_and_governance',
                'method': 'speed_and_governance_measurement', 'value_type': 'object',
                'kind': 'measured', 'inputs': ['road.xodr', 'sign-survey.json',
                    'street-status.json', 'actor-poses.jsonl']}],
            'negative': {'remove': ['sign-survey.json'],
                'error_contains': 'Missing required source: sign-survey.json'}}
        (path.parent.parent / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (HERE / 'proposals').mkdir(exist_ok=True)
    (HERE / 'proposals/cases.json').write_text(json.dumps({'cell_id': 'C179819',
        'actor': 'motor_vehicle_driver', 'status': 'draft', 'sweeps_expanded': True,
        'cases': proposal_cases}, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
