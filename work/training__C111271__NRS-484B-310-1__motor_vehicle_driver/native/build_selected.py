"""Materialize six exact selected flashing-red constructions and contracts."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / 'native'
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
SOURCES = ('native.jsonl', 'video_frames.jsonl', 'geometry.json')
IMPLEMENTATION = ('runner.py', 'capture.py', 'controller.py', 'measure.py', 'finalize.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, value):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / (path.name + '.staging')
    stage.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    os.replace(stage, path)


def test_source():
    return '''import unittest
from controller import State, command
from runner import check
from capture import survey_for


class ExactFlashingRedTest(unittest.TestCase):
    def test_exact_bundle_and_controller(self):
        result = check()
        self.assertEqual(result['exact_cases_checked'], 6)
        self.assertFalse(result['native_executed'])
        for stop, no_stop, reference in (
                ('probe_a', 'probe_b', 48.0),
                ('crosswalk_stop', 'crosswalk_no_stop', 50.0),
                ('intersection_stop', 'intersection_no_stop', 52.0)):
            self.assertEqual(command(stop, reference - 2, 5, reference, False, State())['engineering_phase'], 'pre_reference_stop')
            self.assertEqual(command(no_stop, reference - 2, 5, reference, False, State())['engineering_phase'], 'proceed')

    def test_missing_original_survey_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Original Native context survey required'):
            survey_for('case__probe_a', '/unavailable/original-survey.json')


if __name__ == '__main__':
    unittest.main()
'''


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    base = json.loads((NATIVE / 'config.json').read_text())
    rows = []
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        cfg = dict(base)
        cfg['case_id'] = case_id
        cfg['selected_case_id'] = case_id
        cfg['reference_kind'] = case['reference_kind']
        cfg['requested_halt'] = case['halt_requested']
        cfg['limit_line_x_m'] = 48.0 if case['reference_kind'] == 'limit_line' else None
        cfg['crosswalk_near_x_m'] = 50.0 if case['reference_kind'] != 'intersection' else None
        cfg['intersection_near_x_m'] = 52.0
        cfg['case'] = {'case_id': case_id, 'recording_description': cfg['recording_description']}
        target = ROOT / 'cases' / suffix
        target.mkdir(parents=True, exist_ok=True)
        files = []
        for name in IMPLEMENTATION:
            content = (NATIVE / name).read_text()
            (target / name).write_text(content)
            files.append({'path': name, 'content': content})
        config_text = json.dumps(cfg, indent=2, ensure_ascii=False) + '\n'
        (target / 'config.json').write_text(config_text)
        files.append({'path': 'config.json', 'content': config_text})
        tests = test_source()
        (target / 'tests').mkdir(exist_ok=True)
        (target / 'tests/test_offline.py').write_text(tests)
        files.append({'path': 'tests/test_offline.py', 'content': tests})
        construction = {
            'format': 'worker-inline-construction', 'entrypoint': 'runner.py',
            'case_id': case_id, 'law_id': plan['law_id'],
            'cell_id': plan['cell_id'], 'actor': plan['actor'],
            'files': files, 'recording_description': cfg['recording_description'],
            'measurement_plan': {'entrypoint': 'finalize.py',
                                 'required_sources': list(SOURCES)},
            'static_checks': ['exact original-survey identity and stopping-reference hierarchy',
                              '20-Hz 600-frame red/off source and four-camera join',
                              'no legal verdict from requested stopping control'],
            'termination_rules': ['600 original Native frames',
                                  'close four encoders and recorder, restore Native world'],
            'mechanisms': ['surveyed official facing signal and reference',
                           'pre-reference stop versus nonstop controller',
                           'measured body and post-stop conflict source'],
            'status': 'selected_cpu_preparation'}
        construction_path = target / 'construction.json'
        atomic(construction_path, construction)
        disposition = next((i, item) for i, item in enumerate(plan['requirement_dispositions'])
                           if case_id in item['case_ids'])
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [{'disposition_index': disposition[0],
                                      'requirement': disposition[1]['requirement'],
                                      'source': disposition[1]['source'],
                                      'output_key': 'flashing_red_stop',
                                      'method': 'flashing_red_stop', 'value_type': 'object',
                                      'kind': 'measured', 'inputs': list(SOURCES)}],
                    'negative': {'remove': ['geometry.json'],
                                 'error_contains': 'Missing required source: geometry.json'}}
        contract_path = ROOT / ('measurement-' + suffix + '.json')
        atomic(contract_path, contract)
        rows.append({'case_id': case_id,
                     'kind': 'delivery',
                     'construction': str(construction_path.relative_to(ROOT)),
                     'construction_sha256': sha(construction_path),
                     'fixture_recipe': str((ROOT / ('selected-recipe-' + suffix + '.json')).relative_to(ROOT.parents[1])),
                     'measurement_contract': contract_path.name,
                     'measurement_procedure': {'entrypoint': 'finalize.py',
                                               'output_schema': 'worker-c111271-flashing-red-analysis-v1'},
                     'candidate_risk': {'status': 'none',
                                        'reason': 'Original signal governance or stopping reference must be source-reviewed; no fallback can substitute for missing original authority while preserving this exact comparison.'},
                     'candidates': []})
        if suffix == 'probe_a':
            for file in files:
                path = ROOT / file['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(file['content'])
            atomic(ROOT / 'construction.json', construction)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': plan['assignment_id'],
                'runtime_manifest_sha256': sha(Path('runtime/SOURCE-MANIFEST.json')),
                'cases': rows}
    atomic(ROOT / 'selected-preflight-manifest.json', manifest)
    return {'selected_cases': len(rows),
            'preflight_manifest_sha256': sha(ROOT / 'selected-preflight-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build()))
