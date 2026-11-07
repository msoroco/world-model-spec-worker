"""Build exact unselected offline bundles for the official vehicle branch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
ASSIGNMENT = FOLDER.name
CASES = ('official_1', 'official_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = ('runner.py', 'geometry.py', 'candidates.py', 'statutory-scope.json',
           'measure_saved.py', 'prepare_saved.py', 'finalize.py')
TEST = '''import hashlib
import json
from pathlib import Path
import unittest
from runner import check
from candidates import construction
from geometry import requested_tracks, native_track_requests

class OfficialConstructionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_request_and_preflight(self):
        case, candidate = self.config['case_suffix'], self.config['candidate_id']
        plan = construction(case, candidate)
        self.assertTrue(check(case, candidate)['passed'])
        self.assertEqual(check(case, candidate)['native_track_rows'], 480)
        self.assertEqual(check(case, candidate)['camera_count'], 4)
        self.assertFalse(check(case, candidate)['carla_imported'])
        rows = native_track_requests(case, **plan['knobs'])
        source = ''.join(json.dumps(row, sort_keys=True) + '\\n' for row in rows).encode()
        self.assertEqual(hashlib.sha256(source).hexdigest(), self.config['native_requests_sha256'])
        self.assertTrue(all(r['approach_role_request'] == 'official_vehicle_of_regulatory_agency'
                            and r['lamp_request']['qualification_unverified'] for r in rows))
        self.assertFalse(self.config['vehicle_authority_verified'])

    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):
            check('unrelated', self.config['candidate_id'])

if __name__ == '__main__':
    unittest.main()
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    source = json.loads((HERE / 'drafts/manifest.json').read_text())
    assert len(source['cases']) == 8
    batch = json.loads((REPO / 'batch.json').read_text())
    files = [{'path': name, 'content': (HERE / name).read_text()} for name in SOURCES]
    files.append({'path': 'tests/test_construction.py', 'content': TEST})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'source_branch': 'official_regulatory_vehicle_approach', 'cases': []}
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case
        entry = {'case_id': case_id, 'kind': 'draft_not_selected', 'candidates': [],
                 'measurement_contract': f'measurement-contracts/{case}.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c405647-1a-saved-analysis-v1'},
                 'candidate_risk': {'status': 'physical_and_source_review',
                                    'reason': 'Agency authority, incorporated lamps and Native motion unverified'}}
        contract = {'format': 'worker-measurement-contract-v1', 'case_id': case_id,
                    'requirements': [{'disposition_index': 0,
                                      'requirement': 'NRS-484B-267-1a',
                                      'source': 'NRS 484B.267(1)(a)',
                                      'output_key': 'official_approach_clearance',
                                      'method': 'approach_clearance_and_lamp_timing',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['source-scope.json', 'actor-frames.jsonl']}],
                    'negative': {'remove': ['source-scope.json'],
                                 'error_contains': 'Missing required source: source-scope.json'}}
        write(HERE / 'measurement-contracts' / (case + '.json'), contract)
        for candidate in CANDIDATES:
            draft = HERE / 'drafts' / case / candidate
            authored = json.loads((draft / 'config.json').read_text())
            assert authored['status'] == 'unselected_cpu_draft'
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'supported_case_ids': [case_id], 'case': {'case_id': case_id},
                      'case_suffix': case, 'candidate_id': candidate,
                      'cell_id': 'C405647', 'law_id': 'NRS-484B-267-1a',
                      'actor': 'motor_vehicle_driver', 'duration_s': 24, 'rate_hz': 20,
                      'source_branch': 'official_regulatory_vehicle_approach',
                      'required_atoms': ['rel.same_direction', 'rel.surface_gap',
                                         'kin.position', 'rel.occupies'],
                      'native_requests_sha256': authored['native_requests_sha256'],
                      'authored_config_sha256': sha(draft / 'config.json'),
                      'case_specific_saved_observables': {
                          'official_regulatory_agency_authority': 'source-bound agency record and original Native actor identity',
                          'qualifying_flashing_lights': 'original pixel review and exact NRS 484A.480(3) source'},
                      'cameras': [{'name': x, 'width': w, 'height': h} for x, w, h in (
                          ('overview', 1920, 1080), ('front_lamp', 1280, 720),
                          ('rear_approach', 1280, 720), ('subject_reference', 1280, 720))],
                      'vehicle_authority_verified': False, 'lamp_qualification_verified': False,
                      'physical_success_claimed': False, 'status': 'unselected_native_runner_prototype'}
            construction = {'case_id': case_id, 'cell_id': 'C405647',
                            'law_id': 'NRS-484B-267-1a', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py',
                            'files': files + [{'path': 'config.json',
                                               'content': json.dumps(config, indent=2) + '\n'}],
                            'measurement_plan': {'method': 'saved Native actor/body and original pixel review',
                                                 'status': 'unselected_not_yet_implemented'},
                            'recording_description': {'channels': [
                                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                                 'method': 'original Native frame join',
                                 'time_window': '480 frames',
                                 'reference_frame': 'Native imported OpenDRIVE',
                                 'uncertainty': '50 ms frame bracket'}
                                for name in ('subject_pose_body', 'approach_pose_body',
                                             'light_state', 'camera_frame_join')],
                                'context_inputs': [],
                                'limitations': ['authority and lamp qualification are unverified']},
                            'static_checks': ['paired 480-frame request and four-camera preflight'],
                            'termination_rules': ['retain capture/restoration error', '480 frame joins'],
                            'mechanisms': ['same frozen-cell controlled approach',
                                           'observed-pose actor control', 'four lossless cameras'],
                            'status': 'unselected_cpu_draft'}
            relative = f'package-candidates/{case}/{candidate}/construction.json'
            target = HERE / relative
            write(target, construction)
            ref = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(target)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                ref['trigger'] = authored['trigger']
                ref['changed_knobs'] = {'fallback1': ['lane_change_start_s', 'overview_camera'],
                                        'fallback2': ['approach_start_x_m'],
                                        'fallback3': ['subject_speed_mps', 'front_lamp_fov']}[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE / 'package-manifest.json', manifest)
    return {'case_count': 2, 'candidate_count': 8,
            'manifest_sha256': sha(HERE / 'package-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
