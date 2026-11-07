"""Materialize eight exact, unselected C405647 1(a) CPU constructions."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
NATIVE = FOLDER / 'native'
ASSIGNMENT = FOLDER.name
CASES = ('witness_1', 'witness_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = ('runner.py', 'geometry.py', 'candidates.py', 'source-scope.json',
           'measure_saved.py', 'finalize.py', 'trigger_evidence.py')
TEST = '''import json
from pathlib import Path
import unittest
from runner import check


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_preflight(self):
        result = check(self.config['case_suffix'], self.config['candidate_id'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['native_track_rows'], 480)
        self.assertEqual(result['camera_count'], 4)
        self.assertFalse(result['carla_imported'])

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(ValueError):
            check(self.config['case_suffix'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
'''


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    policies = json.loads((FOLDER / 'draft-construction/candidate-manifest.json').read_text())
    assert policies['assignment_id'] == ASSIGNMENT
    by_key = {(row['case_suffix'], row['candidate_id']): row for row in policies['cases']}
    assert len(by_key) == 8
    code = [{'path': name, 'content': (NATIVE / name).read_text()} for name in SOURCES]
    code.append({'path': 'tests/test_construction.py', 'content': TEST})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'cases': []}
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'measurement_contract': f'draft-measurements/{case}-contract.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c405647-1a-saved-analysis-v1'},
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Native tracking, vehicle authority and original lamp pixels require review'},
                 'candidates': []}
        for candidate in CANDIDATES:
            policy = by_key[(case, candidate)]
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'case_suffix': case, 'candidate_id': candidate,
                      'supported_case_ids': [case_id], 'case': {'case_id': case_id},
                      'cell_id': 'C405647', 'law_id': 'NRS-484B-267-1a',
                      'actor': 'motor_vehicle_driver', 'duration_s': 24, 'rate_hz': 20,
                      'required_atoms': ['ru.emergency_vehicle', 'sig.warning_lamp',
                                         'rel.same_direction', 'rel.surface_gap',
                                         'kin.position', 'rel.occupies'],
                      'source_packets': [],
                      'cameras': [{'name': name, 'width': width, 'height': height,
                                   'pose_strategy': 'candidate-specific candidates.py'}
                                  for name, width, height in (
                                      ('overview', 1920, 1080), ('front_lamp', 1280, 720),
                                      ('rear_approach', 1280, 720), ('subject_reference', 1280, 720))],
                      'status': 'unselected_native_runner_prototype'}
            recording = {'channels': [
                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': 'Original Native actor/light-state and four-camera frame join',
                 'time_window': 'entire 24 s / 480 frame attempt',
                 'reference_frame': 'Native imported OpenDRIVE and original frame',
                 'uncertainty': '50 ms frame bracket; red lamp qualification requires pixels'}
                for name in ('subject_pose_body', 'approach_pose_body', 'light_state', 'camera_frame_join')],
                'context_inputs': [], 'limitations': [
                    'Special1 is not a qualifying red lamp observation',
                    'CPU tracks are requests and not Native observations']}
            files = [*code, {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
            construction = {'case_id': case_id, 'cell_id': 'C405647',
                            'law_id': 'NRS-484B-267-1a', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'measurement_plan': {'method': 'saved original actor/body and pixel review',
                                                 'status': 'prototype_not_runtime_compatible'},
                            'recording_description': recording,
                            'static_checks': ['paired OpenDRIVE tracks and candidate CPU preflight'],
                            'termination_rules': ['480 original frame joins',
                                                  'failure retained on capture or restoration error'],
                            'mechanisms': ['same frozen-cell paired approach',
                                           'observed-pose actor control', 'four lossless cameras'],
                            'status': 'unselected_cpu_draft'}
            relative = f'draft-candidates/{case}/{candidate}/construction.json'
            target = FOLDER / relative
            _write(target, construction)
            ref = {'id': candidate, 'construction': relative, 'construction_sha256': _sha(target)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                ref['trigger'] = {'source': 'saved actor/pixel packet',
                                  'metric': policy['trigger'],
                                  'failure_condition': policy['trigger']}
                ref['changed_knobs'] = {
                    'fallback1': ['lane_change_start_s', 'overview_camera'],
                    'fallback2': ['approach_start_x_m'],
                    'fallback3': ['subject_speed_mps', 'front_lamp_fov']}[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    _write(FOLDER / 'draft-execution-manifest.json', manifest)
    return {'passed': True, 'case_count': 2, 'bundle_count': 8,
            'manifest_sha256': _sha(FOLDER / 'draft-execution-manifest.json'),
            'ready_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
