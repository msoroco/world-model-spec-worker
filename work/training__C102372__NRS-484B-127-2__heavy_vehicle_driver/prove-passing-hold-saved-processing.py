"""Full saved Core/Lean/video synthetic proof for the no-passing control."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-passing-hold-saved'
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from finalize import finalize
from measure_gap import sha
from passing_hold_engineering import ASSIGNMENT,CASE
from passing_hold_trigger import extract
from scenario_pipeline.worker_exchange.measurement_contract import verify_report


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    saved=module('passing_saved_fixture',HERE/'prove-passing-saved-processing.py')
    saved.fixture=module('hold_engineering_fixture',HERE/'prove-passing-hold-engineering.py')
    saved.CASE=CASE;saved.extract=extract
    OUT.mkdir(parents=True,exist_ok=True)
    positive=OUT/'passing_hold-positive';saved.make(positive)
    negative=OUT/'passing_hold-negative'
    if negative.exists():shutil.rmtree(negative)
    shutil.copytree(positive,negative)
    report=finalize(positive,positive/'analysis-report.json')
    contract=json.loads((HERE/'native/measurement-contract-passing_hold.json').read_text())
    verify_report(contract,report,positive)
    result=json.loads((positive/'result.json').read_text())
    measured=result['measured_values']['truck_passing_sequence']
    if not result['target_checks'][0]['matched'] or result['accepted'] or \
       measured['passing_sequence_observed'] is not False or \
       measured['opposing_lane_frames']!=0:
        raise ValueError('Hold saved target or scope differs')
    (negative/'native_samples.jsonl').unlink()
    try:finalize(negative,negative/'analysis-report.json')
    except ValueError as error:
        if 'Missing required source: native_samples.jsonl' not in str(error):raise
    else:raise AssertionError('Missing hold Native source accepted')
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,'frames':480,
            'video_frames':report['video_frames'],
            'minimum_body_clearance_m':measured['minimum_body_clearance_m'],
            'source_sha256':sha(positive/'native_samples.jsonl'),
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
