"""Bind the exact 3(a) source requirement to a saved case measurement."""
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate,verify_report
sys.path.insert(0,str(FOLDER/'native'))
from finalize import analysis_report


def build():
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    source=plan['requirement_dispositions'][0]
    output=FOLDER/'draft-measurements';output.mkdir(exist_ok=True)
    results=[]
    for suffix in ('controlled_1','controlled_2'):
        case_id=plan['assignment_id']+'__'+suffix
        contract={'format':'worker-measurement-contract-v1','case_id':case_id,
                  'requirements':[{'disposition_index':0,
                    'requirement':source['requirement'],'source':source['source'],
                    'output_key':'center_turn_purpose_and_movement',
                    'method':'purpose_movement','value_type':'object','kind':'measured',
                    'inputs':['scene.xodr','road_geometry.json','declared_purpose.json','native_samples.jsonl']}],
                  'negative':{'remove':['declared_purpose.json'],
                              'error_contains':'Missing required source: declared_purpose.json'}}
        path=output/(suffix+'-contract.json')
        path.write_text(json.dumps(contract,indent=2)+'\n')
        validate(contract,plan['requirement_dispositions'],(FOLDER/'native/finalize.py').read_text(),case_id)
        fixture=FOLDER/'synthetic-local'/suffix
        report=analysis_report(fixture)
        report_path=fixture/'finalizer-analysis-report.json'
        report_path.write_text(json.dumps(report,indent=2)+'\n')
        verify_report(contract,report,fixture)
        results.append({'case':suffix,'contract':str(path.relative_to(FOLDER)),
                        'positive_synthetic_measurement_verified':True})
    return results


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
