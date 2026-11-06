"""Full 480-frame synthetic saved processing for both conditions cases."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-conditions-saved'
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from conditions_engineering import ASSIGNMENT,CASES
from conditions_trigger import extract
from finalize import finalize
from measure_gap import sha
from scenario_pipeline.worker_exchange.measurement_contract import verify_report


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    fixture=module('conditions_engineering_fixture',HERE/'prove-conditions-engineering.py')
    saved=module('passing_saved_fixture',HERE/'prove-passing-saved-processing.py')
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    for case in CASES:
        source=fixture.write_case(case)
        positive=OUT/(case+'-positive')
        saved.make(positive,source=source,case=case,
                   trigger=lambda root,case=case:extract(root,case),
                   source_format='c102372-conditions-source-v1',
                   measurement_channel='surface_gap_m')
        negative=OUT/(case+'-negative')
        if negative.exists():shutil.rmtree(negative)
        shutil.copytree(positive,negative)
        report=finalize(positive,positive/'analysis-report.json')
        contract=json.loads((HERE/'native'/('measurement-contract-'+case+'.json')).read_text())
        verify_report(contract,report,positive)
        result=json.loads((positive/'result.json').read_text())
        measured=result['measured_values']['truck_conditions_event']
        if measured['lead_braking_gap_compression_observed']!=(case=='conditions_lead_brake') or \
           result['target_checks'][0]['matched'] is not True or result['accepted'] is not False:
            raise ValueError('Conditions saved target/scope differs')
        (negative/'native_samples.jsonl').unlink()
        try:finalize(negative,negative/'analysis-report.json')
        except ValueError as error:
            if 'Missing required source: native_samples.jsonl' not in str(error):raise
        else:raise AssertionError('Missing conditions Native source accepted')
        results[case]={'frames':480,'video_frames':report['video_frames'],
                       'measured_event':measured['lead_braking_gap_compression_observed'],
                       'minimum_surface_gap_m':measured['minimum_surface_gap_m'],
                       'source_sha256':sha(positive/'native_samples.jsonl')}
    return {'passed':True,'cases':results,'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
