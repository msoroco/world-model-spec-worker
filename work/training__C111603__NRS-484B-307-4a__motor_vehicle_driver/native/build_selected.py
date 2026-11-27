"""Materialize exact inline green-arrow bundles and measurement contracts."""

import hashlib
import json
import os
from pathlib import Path

from build_config import AID, build
from controller import SUFFIXES

ROOT=Path(__file__).resolve().parent.parent
NATIVE=ROOT/'native'
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
SOURCES=('intersection-context.json','signal_frames.jsonl','motion_frames.jsonl',
         'native.jsonl','video_frames.jsonl')
IMPLEMENTATION=('runner.py','capture.py','controller.py','survey.py',
                'build_config.py','arrow_measure.py','finalize.py')
OUTPUT_KEYS={0:'direction_and_entry_source',1:'arrow_program_source',
             2:'participant_priority_source',3:'participant_priority_source'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path,value):
    SCRATCH.mkdir(parents=True,exist_ok=True)
    stage=SCRATCH/('c111603-'+path.parent.name+'-'+path.name+'.stage')
    stage.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    os.replace(stage,path)


def test_source():
    return '''import unittest
from runner import check
from survey import load

class GreenArrowSelectedTest(unittest.TestCase):
    def test_exact_controller_branches(self):
        result=check()
        self.assertEqual(result['exact_cases_checked'],8)
        self.assertFalse(result['native_executed'])
        self.assertEqual(result['controller_phases']['pedestrian_yield'],'pause_for_observed_pedestrian')
        self.assertEqual(result['controller_phases']['traffic_yield'],'pause_for_observed_traffic')

    def test_original_governing_survey_required(self):
        with self.assertRaisesRegex(ValueError,'Original governed-arrow intersection survey required'):
            load('/unavailable/original-survey.json','case__direction_indicated')

if __name__=='__main__':
    unittest.main()
'''


def build_all():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    entries=[]
    for suffix in SUFFIXES:
        case_id=AID+'__'+suffix
        cfg=build(suffix)
        target=ROOT/'cases'/suffix
        target.mkdir(parents=True,exist_ok=True)
        files=[]
        for name in IMPLEMENTATION:
            content=(NATIVE/name).read_text()
            (target/name).write_text(content)
            files.append({'path':name,'content':content})
        config_text=json.dumps(cfg,indent=2,ensure_ascii=False)+'\n'
        (target/'config.json').write_text(config_text)
        files.append({'path':'config.json','content':config_text})
        test=test_source()
        (target/'tests').mkdir(exist_ok=True)
        (target/'tests'/'test_offline.py').write_text(test)
        files.append({'path':'tests/test_offline.py','content':test})
        construction={
            'format':'worker-inline-construction','entrypoint':'runner.py',
            'case_id':case_id,'law_id':plan['law_id'],'cell_id':plan['cell_id'],
            'actor':plan['actor'],'files':files,
            'recording_description':cfg['recording_description'],
            'measurement_plan':{'entrypoint':'finalize.py','required_sources':list(SOURCES)},
            'static_checks':['original surveyed governed arrow head and approach',
                'ego indicated/contrary turn and actual signal state',
                'adjacent crosswalk pedestrian and other intersection vehicle',
                '600-frame original Native/four-camera join',
                'independent pixels, lawful status and yielding review remains open'],
            'termination_rules':['600 original Native frames',
                'close four encoders and recorder, restore Native world'],
            'mechanisms':['source-surveyed intersection, head and turn routes',
                'ego, pedestrian and other vehicle with original Native poses',
                'observed signal and participant state drive eight exact requests'],
            'status':'selected_cpu_preparation'}
        construction_path=target/'construction.json'
        atomic(construction_path,construction)
        rows=[]
        for i,disposition in enumerate(plan['requirement_dispositions']):
            if case_id not in disposition['case_ids']:
                continue
            method=OUTPUT_KEYS[i]
            inputs=list(SOURCES[:3]) if i==0 else [SOURCES[0],SOURCES[1]] if i==1 else [SOURCES[0],SOURCES[2]]
            rows.append({'disposition_index':i,'requirement':disposition['requirement'],
                'source':disposition['source'],'output_key':method,
                'method':method,'value_type':'object','kind':'measured',
                'inputs':inputs})
        contract={'format':'worker-measurement-contract','case_id':case_id,
            'requirements':rows,
            'negative':{'remove':['intersection-context.json'],
                        'error_contains':'Missing required source: intersection-context.json'}}
        contract_path=ROOT/('measurement-'+suffix+'.json')
        atomic(contract_path,contract)
        entries.append({'case_id':case_id,'kind':'delivery',
            'construction':str(construction_path.relative_to(ROOT)),
            'construction_sha256':sha(construction_path),
            'fixture_recipe':str((ROOT/('selected-recipe-'+suffix+'.json')).relative_to(ROOT.parents[1])),
            'measurement_contract':contract_path.name,
            'measurement_procedure':{'entrypoint':'finalize.py',
                'output_schema':'worker-c111603-arrow-analysis-v1'},
            'candidate_risk':{'status':'physical',
                'reason':'Original arrow-only display, approach visibility and participant timing may fail; a surveyed fallback route/camera adjustment must be proved before dispatch.'},
            'candidates':[]})
        if suffix==SUFFIXES[0]:
            for item in files:
                path=ROOT/item['path'];path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(item['content'])
            atomic(ROOT/'construction.json',construction)
    manifest={'format':'worker-execution-manifest','assignment_id':AID,
        'runtime_manifest_sha256':sha(Path('runtime/SOURCE-MANIFEST.json')),
        'cases':entries}
    atomic(ROOT/'selected-preflight-manifest.json',manifest)
    return {'selected_cases':len(entries),'preflight_manifest_sha256':sha(ROOT/'selected-preflight-manifest.json')}


if __name__=='__main__':
    print(json.dumps(build_all(),sort_keys=True))
