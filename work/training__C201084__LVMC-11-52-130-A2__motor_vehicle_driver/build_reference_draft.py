"""Package the current source-bound reference primary for pinned offline proof."""
import hashlib
import json
from pathlib import Path

from native_capture import CAMERA_SPECS


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ('runner.py', 'native_runner.py', 'native_controller.py',
           'native_capture.py', 'native_survey.py', 'fire_lane_survey.py',
           'source_measurement.py', 'native_finalize.py')
CASE = HERE.name+'__reference'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n')


def build():
    plan = json.loads((HERE/'case-plan.json').read_text())
    require_cases = [entry for entry in plan['cases'] if entry['case_id'] == CASE]
    if len(require_cases) != 1:
        raise ValueError('Reference case is absent from the source plan')
    recording = {
        'channels': [{
            'name': entry['name'], 'unit': entry['unit'],
            'sampling_rate_hz': 20,
            'reference_frame': 'original CARLA frame and four video sources',
            'time_window': 'all 600 frames / 30 seconds',
            'method': 'source_measurement from retained actor, frame, survey and video files',
            'uncertainty': '50 ms sample clock; sign face and legal designation require independent review'
        } for entry in plan['observations']],
        'context_inputs': [{
            'name': 'original_map_sign_and_fire_lane_survey',
            'unit': 'structured',
            'method': 'live CARLA map and sign actor readback plus authored geometry',
            'reference_frame': 'surveyed CARLA map',
            'uncertainty': 'Fire Code designation and visible sign text unverified'
        }],
        'limitations': ['No legal or physical conclusion from authored geometry',
                        'Original pixels, posting and statutory exceptions need review']}
    config = {
        'assignment_id': HERE.name, 'case_id': CASE,
        'selected_case_id': CASE, 'case_suffix': 'reference',
        'law_id': 'LVMC-11-52-130-A2', 'cell_id': 'C201084',
        'actor': 'motor_vehicle_driver', 'candidate_id': 'primary',
        'rate_hz': 20, 'frames': 600, 'duration_s': 30,
        'comparison_variable': 'vehicle_stops_in_posted_fire_lane',
        'comparison_requested_value': True,
        'cameras': [{'name': spec[0], 'width': spec[1],
                     'height': spec[2], 'fov_deg': 90,
                     'pose_strategy': 'surveyed_ego_relative'}
                    for spec in CAMERA_SPECS],
        'recording_description': recording,
        'source_packets': [], 'required_atoms': [],
        'survey_contract': {'live_map_and_sign_readback_required': True,
                            'capture_frames': 600},
        'physical_acceptance_claimed': False, 'legal_verdict': None,
    }
    bundle_test = '''import json
import unittest
from pathlib import Path
import runner

class BundleTest(unittest.TestCase):
    def test_exact_primary(self):
        checked = runner.check()
        config = json.loads((Path(__file__).parents[1]/'config.json').read_text())
        self.assertEqual(checked['case_id'], config['case_id'])
        self.assertEqual(checked['frames'], 600)
        self.assertEqual(len(checked['source_cameras']), 4)
        self.assertFalse(checked['physical_acceptance_claimed'])
'''
    files = [{'path': name, 'content': (HERE/name).read_text()}
             for name in MODULES]
    files += [{'path': 'config.json',
               'content': json.dumps(config, indent=2, sort_keys=True)+'\n'},
              {'path': 'tests/test_bundle.py', 'content': bundle_test}]
    construction = {
        'format': 'worker-construction',
        'status': 'selected_cpu_preparation_incomplete',
        'law_id': config['law_id'], 'cell_id': config['cell_id'],
        'actor': config['actor'], 'case_id': CASE,
        'entrypoint': 'runner.py', 'files': files,
        'mechanisms': ['live map and sign actor survey',
                       'source-driven ego and following vehicle stop',
                       'four synchronized original RGB cameras',
                       'retained actor and frame source measurement',
                       'saved-only source finalizer'],
        'raw_sources': ['native-survey-readback.json',
                        'native-actors.jsonl', 'video_frames.jsonl'] +
                       [spec[0]+'.mkv' for spec in CAMERA_SPECS],
        'source_cameras': [spec[0] for spec in CAMERA_SPECS],
        'recording_description': recording,
        'measurement_plan': {
            'source': 'case-plan.json',
            'requirements': plan['requirement_dispositions'],
            'per_case_contracts': [{'case_id': CASE,
                                    'observations': plan['observations']}]},
        'termination_rules': {
            'planned_frames': 600,
            'early_failure': 'survey, actor, camera, frame or source integrity error'},
        'static_checks': ['exact 20 Hz 600-frame reference',
                          'four source cameras',
                          'retained-source video and actor/frame verification'],
    }
    write(HERE/'draft-reference-construction.json', construction)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
                'status': 'draft_primary_offline_only',
                'cases': [{'case_id': CASE,
                           'construction': 'draft-reference-construction.json',
                           'construction_sha256': sha(HERE/'draft-reference-construction.json'),
                           'measurement_contract': 'draft-reference-measurement-contract.json',
                           'fixture_recipe': str((HERE/'draft-reference-diagnostic-recipe.json').relative_to(ROOT)),
                           'measurement_procedure': {
                               'entrypoint': 'native_finalize.py',
                               'source_only': True}}]}
    proposal = dict(require_cases[0])
    proposal['recording_description'] = recording
    proposal['variable_assignments'] = {}
    proposals = HERE/'proposals'
    proposals.mkdir(exist_ok=True)
    write(proposals/'cases.json', {'cases': [proposal]})
    write(HERE/'draft-reference-manifest.json', manifest)
    return {'case_id': CASE,
            'construction_sha256': sha(HERE/'draft-reference-construction.json'),
            'manifest_sha256': sha(HERE/'draft-reference-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
