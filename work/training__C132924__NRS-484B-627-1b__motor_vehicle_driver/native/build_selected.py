"""Materialize four exact roundabout constructions and measurement contracts."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT/'native'
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
SOURCES = ('native.jsonl','video_frames.jsonl','geometry.json')
IMPLEMENTATION = ('runner.py','capture.py','controller.py','measure.py','finalize.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path,value):
    SCRATCH.mkdir(parents=True,exist_ok=True)
    stage = SCRATCH/(path.name+'.stage')
    stage.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    os.replace(stage,path)


def test_source():
    return '''import unittest
from runner import check
from capture import survey_for

class ExactRoundaboutTest(unittest.TestCase):
    def test_four_source_driven_branches(self):
        result = check()
        self.assertEqual(result['exact_cases_checked'], 4)
        self.assertFalse(result['native_executed'])
        self.assertEqual(result['controller_phases']['necessary_pass_after_clearance'], 'return_after_pass')
        self.assertEqual(result['controller_phases']['post_pass_linger_after_clearance'], 'linger_after_pass')

    def test_original_survey_required(self):
        with self.assertRaisesRegex(ValueError, 'Original Native roundabout context survey required'):
            survey_for('case__probe_a', '/unavailable/original-survey.json')

if __name__ == '__main__':
    unittest.main()
'''


def build():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    base = json.loads((NATIVE/'config.json').read_text())
    entries = []
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__',1)[-1]
        cfg = dict(base)
        cfg['case_id'] = case_id
        cfg['selected_case_id'] = case_id
        cfg['case'] = {'case_id':case_id,'recording_description':cfg['recording_description']}
        cfg['passing_exception_case'] = suffix in ('necessary_pass','post_pass_linger')
        target = ROOT/'cases'/suffix
        target.mkdir(parents=True,exist_ok=True)
        files = []
        for name in IMPLEMENTATION:
            content = (NATIVE/name).read_text()
            (target/name).write_text(content)
            files.append({'path':name,'content':content})
        config_text = json.dumps(cfg,indent=2,ensure_ascii=False)+'\n'
        (target/'config.json').write_text(config_text)
        files.append({'path':'config.json','content':config_text})
        (target/'tests').mkdir(exist_ok=True)
        test = test_source()
        (target/'tests/test_offline.py').write_text(test)
        files.append({'path':'tests/test_offline.py','content':test})
        construction = {
            'format':'worker-inline-construction','entrypoint':'runner.py',
            'case_id':case_id,'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':plan['actor'],
            'files':files,'recording_description':cfg['recording_description'],
            'measurement_plan':{'entrypoint':'finalize.py','required_sources':list(SOURCES)},
            'static_checks':['original two marked same-direction Native lane source',
                             'ego body and immediately trailing traffic source',
                             'slower-vehicle pass and clearance source where applicable',
                             '600-frame 20-Hz original Native/four-camera join',
                             'no legal verdict from speed or controller request'],
            'termination_rules':['600 original Native frames',
                                 'close four encoders and recorder, restore Native world'],
            'mechanisms':['surveyed two-lane counterclockwise roundabout',
                          'ego, immediately following vehicle and optional slower vehicle',
                          'source-driven right/left/pass/post-pass controller'],
            'status':'selected_cpu_preparation'}
        construction_path = target/'construction.json'
        atomic(construction_path,construction)
        rows = []
        methods = ('impeding_source','lane_occupancy_source') if suffix in ('probe_a','probe_b') else (
            'impeding_source','passing_source','post_pass_source')
        for i,disposition in enumerate(plan['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            method = methods[len(rows)]
            rows.append({'disposition_index':i,'requirement':disposition['requirement'],
                         'source':disposition['source'],'output_key':method,
                         'method':method,'value_type':'object','kind':'measured',
                         'inputs':list(SOURCES)})
        contract = {'format':'worker-measurement-contract','case_id':case_id,
                    'requirements':rows,
                    'negative':{'remove':['geometry.json'],
                                'error_contains':'Missing required source: geometry.json'}}
        contract_path = ROOT/('measurement-'+suffix+'.json')
        atomic(contract_path,contract)
        entries.append({'case_id':case_id,'kind':'delivery',
                        'construction':str(construction_path.relative_to(ROOT)),
                        'construction_sha256':sha(construction_path),
                        'fixture_recipe':str((ROOT/('selected-recipe-'+suffix+'.json')).relative_to(ROOT.parents[1])),
                        'measurement_contract':contract_path.name,
                        'measurement_procedure':{'entrypoint':'finalize.py',
                                                 'output_schema':'worker-c132924-roundabout-analysis-v1'},
                        'candidate_risk':{'status':'none',
                            'reason':'A different radius or camera cannot substitute for missing original marked-lane or pass-necessity evidence; retain the surveyed exact two-lane scope.'},
                        'candidates':[]})
        if suffix == 'probe_a':
            for file in files:
                path = ROOT/file['path']
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(file['content'])
            atomic(ROOT/'construction.json',construction)
    manifest = {'format':'worker-execution-manifest','assignment_id':plan['assignment_id'],
                'runtime_manifest_sha256':sha(Path('runtime/SOURCE-MANIFEST.json')),
                'cases':entries}
    atomic(ROOT/'selected-preflight-manifest.json',manifest)
    return {'selected_cases':len(entries),'preflight_manifest_sha256':sha(ROOT/'selected-preflight-manifest.json')}


if __name__=='__main__':
    print(json.dumps(build()))
