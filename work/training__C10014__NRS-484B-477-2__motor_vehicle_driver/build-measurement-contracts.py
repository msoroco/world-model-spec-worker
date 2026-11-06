"""Bind both required clause/scope rows to source-hashed draft observations."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate,verify_report


def build():
    plan=json.loads((HERE/'case-plan.json').read_text())
    code=(HERE/'native/measure_entrance.py').read_text()
    output=[]
    for draft in plan['cases']:
        suffix=draft['case_id'].rsplit('__',1)[-1]
        folder=HERE/'draft-measurements'/suffix
        receipt=json.loads((folder/'measurement.json').read_text())
        requirements=[]
        for index,disposition in enumerate(plan['requirement_dispositions']):
            if disposition['status']!='selected_required' or draft['case_id'] not in disposition.get('case_ids',[]):
                continue
            requirements.append({'disposition_index':index,
                'requirement':disposition['requirement'],'source':disposition['source'],
                'output_key':'entrance_overlap_observation' if index==0 else 'alley_stop_context',
                'method':'measure','value_type':'object',
                'kind':'measured' if index==0 else 'sourced_context',
                'inputs':['native_samples.jsonl','road_geometry.json']})
        contract={'format':'worker-measurement-contract-v1','case_id':draft['case_id'],
                  'requirements':requirements,
                  'negative':{'remove':['native_samples.jsonl'],
                              'error_contains':'Missing required source: native_samples.jsonl'}}
        validate(contract,plan['requirement_dispositions'],code,draft['case_id'])
        sources=receipt['source_sha256']
        report={'measurements':{
            'entrance_overlap_observation':{'method':'measure',
                'value':{'max_entrance_overlap_m':receipt['max_entrance_overlap_m'],
                         'mean_entrance_overlap_m':receipt['mean_entrance_overlap_m']},
                'sources':sources},
            'alley_stop_context':{'method':'measure',
                'value':{'first_frame':receipt['stop_first_frame'],
                         'last_frame':receipt['stop_last_frame'],
                         'duration_s':receipt['stop_duration_s'],
                         'native_design_verified':False,
                         'legal_blocking_verdict_claimed':False},
                'sources':sources}}}
        verify_report(contract,report,folder)
        (folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
        (folder/'contract-report.json').write_text(json.dumps(report,indent=2)+'\n')
        output.append({'suffix':suffix,'requirements':len(requirements),
                       'pinned_contract_validate':True,'pinned_saved_value_verify':True,
                       'selected':False})
    result={'format':'c10014-draft-contract-proof-v1','rows':output,
            'scope':'synthetic saved values only; no physical or legal conclusion'}
    (HERE/'draft-measurements/contract-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(build(),indent=2))
