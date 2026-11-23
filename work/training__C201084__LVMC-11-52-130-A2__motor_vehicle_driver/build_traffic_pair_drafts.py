"""Bind the common-controller lead-present/absent probes to draft CPU cases."""
import copy
import hashlib
import json
from pathlib import Path

from native_capture import CAMERA_SPECS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = (
    'traffic_pair_entrypoint.py', 'traffic_pair_runner.py',
    'traffic_pair_capture.py', 'traffic_pair_measurement.py',
    'traffic_pair_finalize.py', 'traffic_pair_controller.py',
    'exception_runner.py', 'exception_capture.py',
    'exception_measurement.py', 'conflict_controller.py',
    'native_runner.py', 'native_capture.py', 'native_controller.py',
    'native_survey.py', 'fire_lane_survey.py', 'source_measurement.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build(mode):
    assert mode in ('near_lead', 'absent_lead')
    case = HERE.name+'__'+mode
    reference = json.loads((HERE/'draft-reference-construction.json').read_text())
    config = json.loads(next(row['content'] for row in reference['files']
                             if row['path'] == 'config.json'))
    config.update(case_id=case, selected_case_id=case, case_suffix=mode,
                  candidate_id='primary', comparison_requested_value=(mode == 'near_lead'))
    config['traffic_pair'] = {
        'destination_xy_m': [30, 1], 'lead_present': mode == 'near_lead',
        'statutory_necessity_verified': False}
    config['recording_description']['channels'].append({
        'name': 'lead_traffic_presence', 'unit': 'bool',
        'sampling_rate_hz': 20,
        'reference_frame': 'original CARLA actor inventory',
        'time_window': 'all 600 frames / 30 seconds',
        'method': 'saved lead actor inventory and pose source join',
        'uncertainty': '50 ms clock; statutory necessity needs original review'})
    config['recording_description']['limitations'].append(
        'Lead presence and braking request do not establish statutory necessity')
    test = '''import json\nimport unittest\nfrom pathlib import Path\nimport traffic_pair_entrypoint\n\nclass BundleTest(unittest.TestCase):\n    def test_exact_pair_primary(self):\n        checked = traffic_pair_entrypoint.check()\n        config = json.loads((Path(__file__).parents[1]/'config.json').read_text())\n        self.assertEqual(checked['case_id'], config['case_id'])\n        self.assertEqual(checked['frames'], 600)\n        self.assertEqual(len(checked['source_cameras']), 4)\n        self.assertFalse(checked['physical_acceptance_claimed'])\n'''
    files = [{'path': name, 'content': (HERE/name).read_text()} for name in MODULES]
    files += [{'path': 'config.json',
               'content': json.dumps(config, indent=2, sort_keys=True)+'\n'},
              {'path': 'tests/test_bundle.py', 'content': test}]
    plan = json.loads((HERE/'case-plan.json').read_text())
    construction = {
        'format': 'worker-construction',
        'status': 'selected_cpu_preparation_incomplete',
        'law_id': config['law_id'], 'cell_id': config['cell_id'],
        'actor': config['actor'], 'case_id': case,
        'entrypoint': 'traffic_pair_entrypoint.py', 'files': files,
        'mechanisms': ['live map and sign actor survey',
                       'common destination beyond authored fire-lane segment',
                       'optional same-road lead vehicle',
                       'source-driven lead relation braking',
                       'four synchronized original RGB cameras',
                       'saved-only actor, survey and video measurement'],
        'raw_sources': ['native-survey-readback.json', 'native-actors.jsonl',
                        'video_frames.jsonl']+[spec[0]+'.mkv' for spec in CAMERA_SPECS],
        'source_cameras': [spec[0] for spec in CAMERA_SPECS],
        'recording_description': config['recording_description'],
        'measurement_plan': {
            'source': 'case-plan.json',
            'requirements': plan['requirement_dispositions'],
            'per_case_contracts': [{'case_id': case,
                'observations': plan['observations']+[
                    {'name': 'lead_traffic_presence', 'unit': 'bool',
                     'mandatory': True, 'purpose': 'Saved actor presence'}]}]},
        'termination_rules': {'planned_frames': 600,
            'early_failure': 'survey, actor, camera, frame or source integrity error'},
        'static_checks': ['exact 20 Hz 600-frame optional-lead probe',
                          'four source cameras', 'retained actor and frame verification']}
    construction_path = HERE/('draft-'+mode+'-construction.json')
    write(construction_path, construction)
    contract = json.loads((HERE/'draft-reference-measurement-contract.json').read_text())
    contract['case_id'] = case
    contract['requirements'][0].update(method='measure_traffic_pair_context',
                                       output_key='traffic_pair_context')
    write(HERE/('draft-'+mode+'-measurement-contract.json'), contract)
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
        'status': 'draft_primary_offline_only',
        'cases': [{'case_id': case,
            'construction': construction_path.name,
            'construction_sha256': sha(construction_path),
            'measurement_contract': 'draft-'+mode+'-measurement-contract.json',
            'fixture_recipe': str((HERE/('draft-'+mode+'-diagnostic-recipe.json')).relative_to(ROOT)),
            'measurement_procedure': {'entrypoint': 'traffic_pair_finalize.py',
                                      'source_only': True}}]}
    write(HERE/('draft-'+mode+'-manifest.json'), manifest)
    proposal = copy.deepcopy(next(row for row in plan['cases']
                                  if row['case_id'] == case))
    proposal['recording_description'] = config['recording_description']
    proposal['variable_assignments'] = {}
    proposals_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposals['cases'] = [row for row in proposals['cases']
                          if row['case_id'] != case] + [proposal]
    write(proposals_path, proposals)
    return {'case_id': case, 'construction_sha256': sha(construction_path),
            'manifest_sha256': sha(HERE/('draft-'+mode+'-manifest.json'))}


if __name__ == '__main__':
    print(json.dumps([build(mode) for mode in ('near_lead', 'absent_lead')], sort_keys=True))
