"""Build three exact source-gated diagnostic bundles for offline proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCES = ('runner.py', 'diagonal_crossing.py', 'native_capture.py',
           'camera_media.py', 'crossing_audit.py', 'saved_crossing.py',
           'reviewed_site.py', 'delivery_audit.py', 'comparison_audit.py',
           'analysis.py')
CASES = ('permissive_whole_crossing', 'prohibitive_whole_crossing',
         'instruction_changes_during_crossing')
DESCRIPTION = {
    'channels': [
        {'name': name, 'unit': unit,
         'method': 'source-sealed original Native readback, all 900 ticks',
         'sampling_rate_hz': 20, 'time_window': 'whole opposite-corner crossing',
         'reference_frame': 'CARLA original world frame',
         'uncertainty': 'physical visibility and official instruction require independent review'}
        for name, unit in (('walker_center_xy', 'm'),
                           ('governing_diagonal_instruction', 'source state'),
                           ('camera_original_frame_map', 'frame'))],
    'context_inputs': [
        {'name': 'reviewed_original_diagonal_site', 'unit': 'source packet',
         'method': 'hash-bound OpenDRIVE, surveyed four corners and official device inventory'},
        {'name': 'NRS_484B_290_exception', 'unit': 'source packet',
         'method': 'independent exception source review, unresolved where absent'}],
    'limitations': ['An authored map or fixture device is not original official diagonal authority.']}
OFFLINE_TEST = '''import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import runner

class ExactBundle(TestCase):
    def test_case_and_four_camera_source_contract(self):
        config = runner.check()
        self.assertEqual(config['selected_case_id'], json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())['selected_case_id'])
        self.assertEqual(config['duration_s'], 45)
        self.assertEqual(len(config['cameras']), 4)

    def test_original_operator_is_required(self):
        with patch.dict('os.environ', {'SCENARIO_C111329_ORIGINAL_OPERATOR': '',
                                      'SCENARIO_C111329_ORIGINAL_OPERATOR_SHA256': ''}):
            with self.assertRaisesRegex(ValueError, 'source-reviewed C111329 Native operator'):
                runner._operator()
'''


def build():
    plan_bytes = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    if {case['case_id'].removeprefix(ASSIGNMENT + '__') for case in plan['cases']} != set(CASES):
        raise ValueError('three exact C111329 diagonal instruction cases required')
    entries = []
    proposals = []
    requirement = plan['requirement_dispositions'][0]
    runtime_sha = json.loads((HERE.parents[1] / 'batch.json').read_text())['runtime']['source_manifest_sha256']
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        config = {
            'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
            'actor': plan['actor'], 'selected_case_id': case_id,
            'supported_case_ids': [row['case_id'] for row in plan['cases']],
            'scenario_parameters': case['scenario_parameters'],
            'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
            'rate_hz': 20, 'duration_s': 45, 'required_atoms': [],
            'source_packets': [], 'diagnostic_only': True,
            'cameras': [{'name': name, 'width': width, 'height': height,
                         'fov_deg': 75, 'pose_strategy': 'complete diagonal walker route and governing device'}
                        for name, width, height in
                        (('overview', 1920, 1080), ('approach', 1280, 720),
                         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))],
            'case': {'case_id': case_id, 'recording_description': DESCRIPTION}}
        files = {name: (HERE / name).read_text() for name in SOURCES}
        files.update({'case-plan.json': plan_bytes.decode(),
                      'config.json': json.dumps(config, indent=2) + '\n',
                      'tests/test_bundle.py': OFFLINE_TEST})
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                        'actor': plan['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': DESCRIPTION,
                        'measurement_plan': {'original': 'full route, device instruction and camera join'},
                        'static_checks': ['exact case, source-gated operator, 900 ticks at 20 Hz'],
                        'termination_rules': {'duration_s': 45,
                                              'failure': 'retain failed original attempt'},
                        'mechanisms': ['source-reviewed Native pedestrian controller',
                                       'original official diagonal-device readback'],
                        'files': [{'path': name, 'content': content} for name, content in files.items()]}
        path = HERE / ('construction-' + suffix + '.json')
        path.write_text(json.dumps(construction, indent=2) + '\n')
        contract_path = HERE / 'cases' / suffix / 'measurement-contract.json'
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(json.dumps({
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0,
                              'requirement': requirement['requirement'],
                              'source': requirement['source'],
                              'output_key': 'diagonal_crossing_device_history',
                              'method': 'measure_diagonal_instruction',
                              'value_type': 'object', 'kind': 'measured',
                              'inputs': ['diagonal-source.json',
                                         'walker-diagonal.jsonl',
                                         'device-diagonal.jsonl',
                                         'camera-frame-joins.jsonl']}],
            'negative': {'remove': ['diagonal-source.json'],
                         'error_contains': 'Missing required source: diagonal-source.json'}
        }, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'diagnostic_source_gated',
                        'construction': path.name,
                        'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'candidate_risk': case['physical_risk_assessment'],
                        'measurement_contract': str(contract_path.relative_to(HERE)),
                        'fixture_recipe': str((HERE / 'cases' / suffix / 'fixture-recipe.json').relative_to(HERE.parents[1])),
                        'measurement_procedure': {'entrypoint': 'analysis.py'}})
        proposals.append({'case_id': case_id, 'target_law_id': plan['law_id'],
                          'target_type': 'boundary_probe', 'rationale': case['purpose'],
                          'variable_assignments': {'governing_diagonal_instruction': {
                              'kind': 'world_setup',
                              'value': case['scenario_parameters']['governing_device_instruction']}},
                          'deliberate_differences': ['observed governing diagonal instruction'],
                          'unresolved_judgment_calls': ['NRS 484B.290 exception source status'],
                          'recording_description': DESCRIPTION})
    proposal_path = HERE / 'proposals' / 'cases.json'
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(json.dumps({'cell_id': plan['cell_id'], 'actor': plan['actor'],
                                         'status': 'diagnostic_source_gated',
                                         'sweeps_expanded': True, 'sweep_specs': [],
                                         'cases': proposals}, indent=2) + '\n')
    (HERE / 'execution-manifest.draft.json').write_text(json.dumps({
        'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': runtime_sha,
        'status': 'diagnostic_original_sources_pending',
        'cases': entries}, indent=2) + '\n')
    return entries


if __name__ == '__main__':
    print('built', len(build()), 'source-gated exact diagnostic bundles')
