"""Bind three exact same-cell speed cases to Native acquisition and saved metering."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
TARGETS = {'probe_a': 75, 'probe_at': 80, 'probe_b': 85}
NAMES = ('runner.py', 'speed_turn.py', 'speed_measure.py', 'finalize.py', 'road.xodr')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def main():
    cases = []
    for suffix, mph in TARGETS.items():
        case = AID + '__' + suffix
        bundle = ROOT / 'cases' / suffix
        bundle.mkdir(parents=True, exist_ok=True)
        for name in NAMES:
            (bundle/name).write_bytes((ROOT/name).read_bytes())
        config = json.loads((ROOT/'draft-native'/suffix/'construction.json').read_text())
        config = json.loads(next(row['content'] for row in config['files'] if row['path'] == 'config.json'))
        config.update({'assignment_id': AID, 'selected_case_id': case, 'supported_case_ids': [AID+'__'+s for s in TARGETS],
                       'candidate_id': 'primary', 'spawn_s_m': 5, 'required_atoms': [], 'source_packets': [],
                       'physical_completion': {},
                       'physical_acceptance_claimed': False,
                       'recording_description': {'channels': [
                           {'name': name, 'unit': unit, 'method': method,
                            'reference_frame': 'original Native C329610 left-turn actor frame',
                            'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
                            'uncertainty': '50 ms sampling; original physical realization and pixels require local review'}
                           for name, unit, method in (
                               ('kin.velocity', 'm/s', 'original three-axis post-tick Native vehicle velocity'),
                               ('kin.speed', 'mph', 'norm of original Native velocity divided by 0.44704'),
                               ('ru.subject', 'identifier', 'original Native actor ID and reviewed vehicle identity'))],
                           'context_inputs': [],
                           'limitations': ['Controller request is not original measured speed',
                                           'CPU fixtures do not establish physical speed or camera visibility']}})
        write(bundle/'config.json', config)
        tests = '''import json\nimport unittest\nfrom pathlib import Path\nimport runner\nfrom speed_turn import check_config\n\nclass SelectedSpeed(unittest.TestCase):\n def test_exact_construction(self):\n  config=json.loads(Path('config.json').read_text())\n  self.assertTrue(runner.check()['passed'])\n  check_config(config,Path('road.xodr').read_text())\n  self.assertIn(config['requested_speed_mph'],(75,80,85))\n  self.assertEqual(runner.requested_speed(10,config['requested_speed_mph']),config['requested_speed_mph']*.44704)\n def test_wrong_scope(self):\n  config=json.loads(Path('config.json').read_text())\n  config['cell_id']='wrong'\n  with self.assertRaises(ValueError):check_config(config,Path('road.xodr').read_text())\n'''
        (bundle/'tests').mkdir(exist_ok=True)
        (bundle/'tests/test_selected.py').write_text(tests)
        files = [{'path': name, 'content': (bundle/name).read_text()}
                 for name in (*NAMES, 'config.json', 'tests/test_selected.py')]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C329610', 'law_id': 'NRS-484B-600-1e',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'measurement_plan': {'method': 'original Native post-tick three-axis velocity and frame/actor join',
                                             'boundary_mph': 80, 'requested_speed_mph': mph,
                                             'legal_tolerance_claimed': False},
                        'static_checks': ['authored same-cell two-way intersection and left-turn road sequence 1,13,4',
                                          '600 original frames at 20 Hz', 'four synchronized source cameras'],
                        'termination_rules': ['600 original frames', 'abort if ego leaves lane or camera frame differs'],
                        'mechanisms': ['source-hashed C329610 OpenDRIVE', 'Native velocity feedback',
                                       'road waypoint left-turn steering'],
                        'recording_description': config['recording_description'], 'files': files}
        path = ROOT / f'selected-{suffix}-primary-construction.json'
        write(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'status': 'selected', 'requirements': [{
                        'disposition_index': 0, 'requirement': 'NRS-484B-600-1e',
                        'source': 'NRS 484B.600(1)(e)', 'kind': 'measured',
                        'method': 'measure_speed', 'output_key': 'speed_observation',
                        'value_type': 'object', 'inputs': [
                            'native_motion.jsonl','road_context.json','video_frames.jsonl',
                            'trace.jsonl','capture/evidence.jsonl']}],
                    'negative': {'remove': ['native_motion.jsonl'],
                                 'error_contains': 'Missing required source: native_motion.jsonl'}}
        contract_path = ROOT/f'selected-{suffix}-measurement-contract.json'
        write(contract_path, contract)
        candidates = []
        if suffix == 'probe_b':
            fallback = json.loads(json.dumps(construction))
            fallback_config = dict(config, candidate_id='fallback1', spawn_s_m=1)
            for row in fallback['files']:
                if row['path'] == 'config.json':
                    row['content'] = json.dumps(fallback_config, indent=2, ensure_ascii=False) + '\n'
            fallback['measurement_plan']['spawn_s_m'] = 1
            fallback_path = ROOT/'selected-probe_b-fallback1-construction.json'
            write(fallback_path, fallback)
            candidates.append({'id': 'fallback1', 'construction': fallback_path.name,
                               'construction_sha256': sha(fallback_path),
                               'changed_knobs': ['subject spawn from road 1 s=5 m to s=1 m'],
                               'trigger': {'source': 'native_motion.jsonl',
                                           'metric': 'maximum_observed_mph_while_driving',
                                           'failure_condition': 'original Native approach velocity never reaches the 85 mph request'}})
        cases.append({'case_id': case, 'kind': 'delivery',
                      'construction': path.name, 'construction_sha256': sha(path),
                      'fixture_recipe': f'work/{AID}/native/diagnostic/{suffix}/fixture-recipe.json',
                      'measurement_contract': contract_path.name,
                      'measurement_procedure': {'entrypoint': 'finalize.py'},
                      'native_handoff': {'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
                      'candidate_risk': {'status': 'physical' if suffix == 'probe_b' else 'none',
                                         'reason': '85 mph request may not be realized before the turn; original Native velocity decides.' if suffix == 'probe_b' else 'No specific additional physical risk beyond ordinary reviewed capture.'},
                      'candidates': candidates})
    write(ROOT/'selected-draft-execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': sha(Path('runtime/SOURCE-MANIFEST.json')),
        'status': 'selected_cpu_proofs_pending', 'cases': cases,
        'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
