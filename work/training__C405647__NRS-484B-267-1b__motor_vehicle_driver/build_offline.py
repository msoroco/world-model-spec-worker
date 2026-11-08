"""Materialize eight exact unselected 1(b) Native bundles for pinned offline CPU."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
NATIVE = FOLDER / 'native'
AID = FOLDER.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = ('runner.py', 'build.py', 'measure_saved.py', 'prepare_original.py')
TEST = '''import json
from pathlib import Path
import unittest
from runner import check
from measure_saved import assignment_hash


class ConstructionTests(unittest.TestCase):
    def test_exact_bundle_preflight(self):
        config = json.loads(Path('config.json').read_text())
        result = check(config['case_suffix'], config['candidate_id'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['native_track_rows'], 480)
        self.assertEqual(result['camera_count'], 4)
        self.assertFalse(result['carla_imported'])

    def test_unknown_variant_rejected(self):
        config = json.loads(Path('config.json').read_text())
        with self.assertRaises(ValueError):
            check(config['case_suffix'], 'unsupported')

    def test_bundled_frozen_assignment_source(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(assignment_hash(), config['assignment_sha256'])


if __name__ == '__main__':
    unittest.main()
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    draft = json.loads((NATIVE / 'drafts' / 'manifest.json').read_text())
    if draft['assignment_id'] != AID or len(draft['cases']) != 8:
        raise ValueError('Right-edge draft construction differs')
    code = [{'path': name, 'content': (NATIVE / name).read_text()} for name in SOURCES]
    code.append({'path': 'tests/test_construction.py', 'content': TEST})
    map_file = NATIVE / 'drafts' / 'road.xodr'
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': AID, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'cases': []}
    for case in CASES:
        case_id = AID + '__' + case
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'measurement_contract': 'native/measurement-contract.json',
                 'measurement_procedure': {'entrypoint': 'measure_saved.py',
                                           'output_schema': 'c405647-1b-saved-geometry-v1'},
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Native edge behavior, authority and original lamp pixels require review'},
                 'candidates': []}
        for candidate in CANDIDATES:
            source = NATIVE / 'drafts' / case / candidate
            draft_config = json.loads((source / 'config.json').read_text())
            config = {**draft_config, 'selected_case_id': case_id,
                      'case_suffix': case, 'supported_case_ids': [case_id],
                      'case': {'case_id': case_id}, 'cell_id': 'C405647',
                      'law_id': 'NRS-484B-267-1b', 'actor': 'motor_vehicle_driver',
                      'duration_s': 24, 'rate_hz': 20,
                      'required_atoms': ['rel.same_direction', 'rel.surface_gap',
                                         'kin.position', 'rel.occupies'],
                      'case_specific_saved_observables': {
                          'right_edge_geometry': 'saved actor center/body, heading and speed',
                          'emergency_vehicle_authority': 'original source review required',
                          'qualifying_flashing_lamp': 'original pixel review required',
                          'signed_shoulder_exception': 'original signage review required'},
                      'source_packets': [],
                      'cameras': [{'name': name, 'width': width, 'height': height,
                                   'pose_strategy': 'candidate-specific runner.py'}
                                  for name, width, height in (
                                      ('overview', 1920, 1080), ('front_lamp', 1280, 720),
                                      ('right_edge', 1280, 720), ('rear_approach', 1280, 720))],
                      'status': 'unselected_native_runner_prototype'}
            files = [*code,
                     {'path': 'assignment-source.json',
                      'content': (ROOT / 'inputs' / AID / 'assignment.json').read_text()},
                     {'path': 'road.xodr', 'content': map_file.read_text()},
                     {'path': 'requested-tracks.jsonl', 'content': (source / 'requested-tracks.jsonl').read_text()},
                     {'path': 'native-requests.jsonl', 'content': (source / 'native-requests.jsonl').read_text()},
                     {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
            recording = {'channels': [
                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': 'Original Native actor and four-camera frame join',
                 'time_window': 'entire 24 s / 480 frame attempt',
                 'reference_frame': 'Native imported OpenDRIVE and original camera frame',
                 'uncertainty': '50 ms frame bracket; legal source qualification separate'}
                for name in ('subject_pose_body_speed', 'approach_pose', 'camera_frame_join')],
                'context_inputs': [], 'limitations': [
                    'Special1 is not a qualifying flashing lamp observation',
                    'CPU tracks are requests and not Native observations']}
            construction = {'case_id': case_id, 'cell_id': 'C405647',
                            'law_id': 'NRS-484B-267-1b', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'measurement_plan': {'method': 'saved original actor/body and pixel review',
                                                 'status': 'prototype_not_runtime_compatible'},
                            'recording_description': recording,
                            'static_checks': ['paired OpenDRIVE tracks and exact candidate CPU preflight'],
                            'termination_rules': ['480 original actor/video frame joins',
                                                  'failure retained on capture or restoration error'],
                            'mechanisms': ['same frozen-cell paired approach',
                                           'observed-pose actor control', 'four lossless cameras'],
                            'status': 'unselected_cpu_draft'}
            relative = f'draft-candidates/{case}/{candidate}/construction.json'
            target = FOLDER / relative
            write(target, construction)
            ref = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(target)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                ref['trigger'] = {'source': 'source-hashed authored 480-frame track',
                                  **draft_config['measured_trigger']}
                ref['changed_knobs'] = {'fallback1': ['lateral_start_frame'],
                                        'fallback2': ['lateral_duration_frames'],
                                        'fallback3': ['front_lamp_fov']}[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER / 'draft-execution-manifest.json', manifest)
    return {'cases': 2, 'bundles': 8,
            'manifest_sha256': sha(FOLDER / 'draft-execution-manifest.json'),
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
