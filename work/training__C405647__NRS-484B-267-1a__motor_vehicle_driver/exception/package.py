"""Materialize exact unselected offline constructions for officer exception."""
import hashlib
import json
from pathlib import Path

from build import ASSIGNMENT, CASES, CANDIDATES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCES = ('runner.py', 'candidates.py', 'build.py', 'official_motion.py',
           'statutory-scope.json', 'measure_saved.py', 'prepare_saved.py',
           'finalize.py')
TEST = '''import hashlib
import json
from pathlib import Path
import unittest
from runner import check
from build import native_requests

class ExceptionConstructionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_native_request_and_preflight(self):
        case = self.config['case_suffix']
        candidate = self.config['candidate_id']
        result = check(case, candidate)
        self.assertTrue(result['passed'])
        self.assertEqual(result['native_track_rows'], 480)
        self.assertEqual(result['camera_count'], 5)
        self.assertFalse(result['carla_imported'])
        source = ''.join(json.dumps(r, sort_keys=True) + '\\n'
                         for r in native_requests(case, candidate)).encode()
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         self.config['native_requests_sha256'])
        self.assertFalse(self.config['officer_direction_verified'])

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(ValueError):
            check(self.config['case_suffix'], 'unrelated')

if __name__ == '__main__':
    unittest.main()
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    draft = json.loads((HERE / 'drafts/manifest.json').read_text())
    assert len(draft['cases']) == 8
    batch = json.loads((REPO / 'batch.json').read_text())
    files = [{'path': name, 'content': (HERE / name).read_text()} for name in SOURCES]
    files.append({'path': 'tests/test_construction.py', 'content': TEST})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'source_branch': 'when otherwise directed by a law enforcement officer',
                'cases': []}
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'candidates': [],
                 'measurement_contract': f'measurement-contracts/{case}.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c405647-exception-saved-analysis-v1'},
                 'candidate_risk': {'status': 'physical_and_source_review',
                                    'reason': 'Officer identity, direction content, recipient, time and qualifying approach unverified'}}
        for candidate in CANDIDATES:
            folder = HERE / 'drafts' / case / candidate
            authored = json.loads((folder / 'config.json').read_text())
            assert authored['status'] == 'unselected_cpu_draft'
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'supported_case_ids': [case_id], 'case': {'case_id': case_id},
                      'case_suffix': case, 'candidate_id': candidate,
                      'cell_id': 'C405647', 'law_id': 'NRS-484B-267-1a',
                      'actor': 'motor_vehicle_driver', 'duration_s': 24, 'rate_hz': 20,
                      'source_branch': manifest['source_branch'],
                      'required_atoms': ['rel.same_direction', 'rel.surface_gap',
                                         'kin.position', 'rel.occupies'],
                      'native_requests_sha256': authored['native_requests_sha256'],
                      'authored_config_sha256': sha(folder / 'config.json'),
                      'cameras': [{'name': name, 'width': width, 'height': height}
                                  for name, width, height in (
                                      ('overview', 1920, 1080),
                                      ('front_lamp', 1280, 720),
                                      ('rear_approach', 1280, 720),
                                      ('subject_reference', 1280, 720),
                                      ('officer_reference', 1280, 720))],
                      'officer_direction_verified': False,
                      'physical_success_claimed': False,
                      'status': 'unselected_native_runner_prototype'}
            construction = {'case_id': case_id, 'cell_id': 'C405647',
                            'law_id': 'NRS-484B-267-1a',
                            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                            'files': files + [{'path': 'config.json',
                                               'content': json.dumps(config, indent=2) + '\n'}],
                            'measurement_plan': {'method': 'source-bound synthetic saved officer cue/approach measurement; original review later',
                                                 'status': 'synthetic_cpu_path_tested'},
                            'recording_description': {'channels': [
                                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                                 'method': 'original Native frame join',
                                 'time_window': '480 frames',
                                 'reference_frame': 'Native imported OpenDRIVE',
                                 'uncertainty': '50 ms frame bracket'}
                                for name in ('subject_pose_body', 'approach_pose_body',
                                             'officer_visual_pose', 'requested_direction',
                                             'camera_frame_join')],
                                'context_inputs': [],
                                'limitations': ['visual officer stand-in and requested direction do not prove communication']},
                            'static_checks': ['paired 480-frame request and five-camera preflight'],
                            'termination_rules': ['retain capture/restoration error', '480 frame joins'],
                            'mechanisms': ['fixed subject and approach tracks across exception pair',
                                           'observed-pose actor control', 'five lossless cameras'],
                            'status': 'unselected_cpu_draft'}
            relative = f'package-candidates/{case}/{candidate}/construction.json'
            target = HERE / relative
            write(target, construction)
            ref = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(target)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                ref['trigger'] = authored['measured_trigger']
                ref['changed_knobs'] = {
                    'fallback1': ['officer_position_x_m'],
                    'fallback2': ['direction_start_frame'],
                    'fallback3': ['direction_duration_frames', 'officer_camera_fov_deg']
                }[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE / 'package-manifest.json', manifest)
    return {'case_count': 2, 'candidate_count': 8,
            'manifest_sha256': sha(HERE / 'package-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
