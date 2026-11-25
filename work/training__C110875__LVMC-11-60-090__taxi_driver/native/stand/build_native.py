"""Bind unselected executable Native taxi requests to current law and profile."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parents[1].name
ROOT = HERE.parents[3]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = {'probe_01': 'right', 'probe_02': 'straight'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    law = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    batch = json.loads((ROOT / 'batch.json').read_text())
    if law['law']['id'] != 'LVMC-11-60-090' or law['actor'] != 'taxi_driver':
        raise ValueError('Frozen taxi assignment changed')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'unselected_native_diagnostic', 'cases': []}
    for suffix, direction in CASES.items():
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [{'name': name, 'unit': unit,
            'sampling_rate_hz': 20, 'method': method,
            'time_window': '600 original Native frames',
            'reference_frame': 'original Native frame and surveyed street topology',
            'uncertainty': '50 ms sampling; authority and physical topology require review',
            'source': 'channels/' + name + '.jsonl'} for name, unit, method in (
                ('ru.taxicab', 'identity', 'original Native blueprint plus external taxi-license review'),
                ('st.curb_zone', 'structured', 'stand landmark, original RGB and independent designation source'),
                ('dev.regulatory_sign', 'structured', 'OpenDRIVE sign landmark, original RGB and notice authority source'),
                ('dev.governs', 'structured', 'sign station joined to stand and first junction topology'),
                ('st.intersection', 'structured', 'ordered Native junction and independent street-identity review'),
                ('drv.turning', 'degrees', 'original observed heading through first junction'),
                ('kin.heading', 'degrees', 'original Native actor heading'),
                ('kin.path_length', 'm', 'original Native position integrated from stand exit'))],
            'context_inputs': [], 'limitations': [
                'Designation, posted notice and taxi licensing need independent source review',
                'Authored road is a request until original Native topology readback']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + key for key in CASES],
                  'candidate_id': 'primary', 'law_id': law['law']['id'],
                  'cell_id': law['cell_id'], 'actor': law['actor'],
                  'statutory_text': law['law']['text'],
                  'requested_first_turn': direction, 'rate_hz': 20,
                  'duration_s': 30, 'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id},
                  'cameras': [{'name': name,
                    'width': 1920 if name == 'overview' else 1280,
                    'height': 1080 if name == 'overview' else 720,
                    'fov_deg': 90,
                    'pose_strategy': 'subject-mounted original RGB' if name in ('approach', 'driver_reference') else 'fixed surveyed roadside original RGB'}
                    for name in CAMERAS],
                  'recording_description': description,
                  'status': 'native_draft_authority_unverified'}
        tests = '''import json\nimport unittest\nfrom pathlib import Path\nfrom runner import check\nfrom geometry import open_drive\nfrom controller import command\n\nclass TaxiNative(unittest.TestCase):\n    def test_exact_geometry_and_source_profile(self):\n        result = check(json.loads(Path('config.json').read_text()))\n        self.assertEqual(result['geometry']['first_choices'], [11, 12])\n        self.assertFalse(result['physical_completion_claimed'])\n        self.assertIn('taxicab-stand-draft', open_drive())\n        self.assertIn('right-turn-notice-draft', open_drive())\n    def test_controller_split(self):\n        self.assertNotEqual(command('right', 79, -1.75, 0, 5)['target_xy_m'],\n                            command('straight', 79, -1.75, 0, 5)['target_xy_m'])\n'''
        files = [{'path': name, 'content': (HERE / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py',
                              'finalize.py')]
        files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                      {'path': 'tests/test_native.py', 'content': tests}])
        construction = {'case_id': case_id, 'law_id': law['law_id'],
            'cell_id': law['cell_id'], 'actor': law['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': {'entrypoint': 'saved.py', 'required_sources': [
                'actor-poses.jsonl', 'video_frames.jsonl',
                'route-survey-native.json']},
            'static_checks': ['two ordered authored street junctions',
                'stand and right-turn sign assets', 'Native waypoint and landmark readback',
                '20 Hz 600 original frames', 'four retained original RGB cameras'],
            'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
            'mechanisms': ['same road, stand, notice, and cameras; first turn direction varies'],
            'status': 'selected_native_draft_authority_unverified'}
        path = HERE / 'native-drafts' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        alternate = json.loads(json.dumps(construction))
        alt_config = dict(config, candidate_id='fallback1', steering_gain=.024)
        next(item for item in alternate['files'] if item['path'] == 'config.json')['content'] = json.dumps(alt_config, indent=2) + '\n'
        alternate['mechanisms'] = ['same road, stand, notice, and cameras; steering gain increases from 0.018 to 0.024']
        alternate['status'] = 'selected_native_fallback_draft_authority_unverified'
        alternate_path = HERE / 'native-drafts' / suffix / 'fallback1-construction.json'
        alternate_path.write_text(json.dumps(alternate, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE.parents[1])),
            'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native taxi route and sign visibility need original review'},
            'candidates': [{'id': 'fallback1',
                'construction': str(alternate_path.relative_to(HERE.parents[1])),
                'construction_sha256': sha(alternate_path),
                'trigger': {'source': 'original Native actor-poses.jsonl and result.json',
                    'metric': 'observed first-junction turn and original sampled path',
                    'failure_condition': 'requested turn indeterminate or sampled path below 100 m with complete original source'},
                'changed_knobs': ['steering_gain 0.018 to 0.024; case/law/route/cameras/duration fixed']}],
            'measurement_contract': 'native/stand/native-drafts/' + suffix + '/measurement-contract.json',
            'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostic-' + suffix + '-recipe.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'acquisition': {
                'ru.taxicab': {'entrypoint': 'runner.py', 'method': 'Native vehicle blueprint and independently reviewed cab license', 'evidence': ['actor-poses.jsonl', 'route-survey.json']},
                'st.curb_zone': {'entrypoint': 'runner.py', 'method': 'Native stand landmark and original source-camera view', 'evidence': ['road.xodr', 'reference_corner.mkv']},
                'dev.regulatory_sign': {'entrypoint': 'runner.py', 'method': 'Native notice landmark and original source-camera view', 'evidence': ['road.xodr', 'reference_corner.mkv']},
                'dev.governs': {'entrypoint': 'runner.py', 'method': 'Original stand, sign and first-junction source join', 'evidence': ['route-survey-native.json', 'route-survey.json']},
                'st.intersection': {'entrypoint': 'runner.py', 'method': 'Native ordered junction readback and independent street review', 'evidence': ['road.xodr', 'route-survey-native.json', 'route-survey.json']},
                'drv.turning': {'entrypoint': 'runner.py', 'method': 'Original observed taxi heading through first junction', 'evidence': ['actor-poses.jsonl', 'video_frames.jsonl']},
                'kin.heading': {'entrypoint': 'runner.py', 'method': 'Original actor heading at each Native frame', 'evidence': ['actor-poses.jsonl']},
                'kin.path_length': {'entrypoint': 'runner.py', 'method': 'Integrated original Native position after stand departure', 'evidence': ['actor-poses.jsonl']}},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'preparation_status': 'incomplete'})
        contract = {'format': 'worker-measurement-contract',
            'case_id': case_id,
            'requirements': [{'disposition_index': 0,
                'requirement': 'LVMC-11-60-090',
                'source': 'inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json',
                'output_key': 'source_bound_first_turn',
                'method': 'first_turn_measurement', 'value_type': 'object',
                'kind': 'measured',
                'inputs': ['road.xodr', 'route-survey.json',
                    'actor-poses.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                    'reference_corner.mkv']}],
            'negative': {'remove': ['route-survey.json'],
                'error_contains': 'Missing required source: route-survey.json'}}
        (path.parent / 'measurement-contract.json').write_text(
            json.dumps(contract, indent=2) + '\n')
    path = HERE.parents[1] / 'execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    proposals = HERE.parents[1] / 'proposals'
    proposals.mkdir(exist_ok=True)
    (proposals / 'cases.json').write_text(json.dumps({
        'cell_id': 'C110875', 'actor': 'taxi_driver',
        'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
        'cases': [{'case_id': ASSIGNMENT + '__baseline',
            'target_law_id': None, 'target_type': 'baseline',
            'rationale': 'Common frozen taxi-stand context before requesting a route.',
            'variable_assignments': {
                'first_intersection_turn_direction': {'kind': 'subject_behavior', 'value': None},
                'requested_first_turn': {'kind': 'controller', 'value': None},
                'notice_posted': {'kind': 'world_setup', 'value': 'authored right-turn notice; authority unverified'}},
            'unresolved_judgment_calls': ['stand designation, notice posting and first street identity'],
            'recording_description': json.loads(next(f['content'] for f in json.loads(
                (HERE / 'native-drafts' / 'probe_01' / 'construction.json').read_text()
                )['files'] if f['path'] == 'config.json'))['recording_description']}] + [
            {'case_id': ASSIGNMENT + '__' + suffix,
            'target_law_id': 'LVMC-11-60-090',
            'target_type': 'first_turn_' + direction,
            'rationale': 'Original first street after designated stand with posted right-turn notice',
            'variable_assignments': {'first_intersection_turn_direction': {
                'kind': 'subject_behavior', 'value': None},
                'requested_first_turn': {'kind': 'controller', 'value': direction},
                'notice_posted': {'kind': 'world_setup', 'value': 'authored right-turn notice; authority unverified'}},
            'unresolved_judgment_calls': ['taxi license and stand/sign authority',
                'physical first street identity'],
            'recording_description': manifest['cases'][i].get('recording_description')
                or json.loads(next(f['content'] for f in json.loads(
                    (HERE / 'native-drafts' / suffix / 'construction.json').read_text()
                    )['files'] if f['path'] == 'config.json'))['recording_description']}
            for i, (suffix, direction) in enumerate(CASES.items())]},
        indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'native_cases': len(build()['cases'])}))
