"""Bind lead-traffic Native construction to an exact draft CPU case."""
import copy
import hashlib
import json
from pathlib import Path

from exception_capture import CAMERA_SPECS


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name+'__clear'
MODULES = ('clear_entrypoint.py', 'exception_runner.py',
           'exception_capture.py', 'exception_measurement.py',
           'clear_finalize.py', 'conflict_controller.py',
           'native_runner.py', 'native_capture.py', 'native_controller.py',
           'native_survey.py', 'fire_lane_survey.py', 'source_measurement.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build():
    reference = json.loads((HERE/'draft-reference-construction.json').read_text())
    config = json.loads(next(row['content'] for row in reference['files']
                             if row['path'] == 'config.json'))
    config.update(case_id=CASE, selected_case_id=CASE,
                  case_suffix='clear', candidate_id='primary',
                  comparison_requested_value=True)
    config['recording_description']['channels'].append({
        'name': 'lead_traffic_relation', 'unit': 'm',
        'sampling_rate_hz': 20,
        'reference_frame': 'original CARLA ego heading and lead actor',
        'time_window': 'all 600 frames / 30 seconds',
        'method': 'saved ego and lead actor pose and velocity source join',
        'uncertainty': '50 ms sample clock; statutory necessity requires original review'})
    config['recording_description']['limitations'].append(
        'Lead beyond fire-lane segment does not establish exception status')
    config['conflict_probe'] = {'lead_survey_required': True,
                                'statutory_necessity_verified': False, 'lead_spawn_xy_m': [35, 1]}
    test = '''import json
import unittest
from pathlib import Path
import clear_entrypoint

class BundleTest(unittest.TestCase):
    def test_exact_clear_primary(self):
        checked = clear_entrypoint.check()
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
              {'path': 'tests/test_bundle.py', 'content': test}]
    construction = {
        'format': 'worker-construction',
        'status': 'selected_cpu_preparation_incomplete',
        'law_id': config['law_id'], 'cell_id': config['cell_id'],
        'actor': config['actor'], 'case_id': CASE,
        'entrypoint': 'clear_entrypoint.py', 'files': files,
        'mechanisms': ['live map and sign actor survey',
                       'same-road lead beyond authored fire-lane segment',
                       'source-driven lead relation braking',
                       'four synchronized original RGB cameras',
                       'saved-only lead, ego and video source measurement'],
        'raw_sources': ['native-survey-readback.json',
                        'native-actors.jsonl', 'video_frames.jsonl']+
                       [spec[0]+'.mkv' for spec in CAMERA_SPECS],
        'source_cameras': [spec[0] for spec in CAMERA_SPECS],
        'recording_description': config['recording_description'],
        'measurement_plan': {
            'source': 'case-plan.json',
            'requirements': json.loads((HERE/'case-plan.json').read_text())[
                'requirement_dispositions'],
            'per_case_contracts': [{'case_id': CASE,
                'observations': json.loads((HERE/'case-plan.json').read_text())[
                    'observations']+[{'name': 'lead_traffic_relation',
                                     'unit': 'm', 'mandatory': True,
                                     'purpose': 'Saved lead position and closing relation'}]}]},
        'termination_rules': {'planned_frames': 600,
            'early_failure': 'survey, actor, camera, frame or source integrity error'},
        'static_checks': ['exact 20 Hz 600-frame clear-lead probe',
                          'four source cameras',
                          'retained lead actor and ego/frame verification']}
    construction_path = HERE/'draft-clear-construction.json'
    write(construction_path, construction)
    contract = json.loads((HERE/'draft-reference-measurement-contract.json').read_text())
    contract['case_id'] = CASE
    contract['requirements'][0].update(method='measure_lead_conflict_context',
                                       output_key='lead_conflict_context')
    write(HERE/'draft-clear-measurement-contract.json', contract)
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
        'status': 'draft_primary_offline_only',
        'cases': [{'case_id': CASE,
            'construction': construction_path.name,
            'construction_sha256': sha(construction_path),
            'measurement_contract': 'draft-clear-measurement-contract.json',
            'fixture_recipe': str((HERE/'draft-clear-diagnostic-recipe.json').relative_to(ROOT)),
            'measurement_procedure': {'entrypoint': 'clear_finalize.py',
                                      'source_only': True}}]}
    write(HERE/'draft-clear-manifest.json', manifest)
    plan = json.loads((HERE/'case-plan.json').read_text())
    proposal = copy.deepcopy(next(row for row in plan['cases']
                                  if row['case_id'] == CASE))
    proposal['recording_description'] = config['recording_description']
    proposal['variable_assignments'] = {}
    proposals_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposals['cases'] = [row for row in proposals['cases']
                          if row['case_id'] != CASE] + [proposal]
    write(proposals_path, proposals)
    return {'case_id': CASE, 'construction_sha256': sha(construction_path),
            'manifest_sha256': sha(HERE/'draft-clear-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
