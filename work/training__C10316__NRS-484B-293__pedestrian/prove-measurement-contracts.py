"""Validate unselected C10316 requirement/source bindings with the pinned checker."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.measurement_contract import validate,verify_report
from native.measure_crosswalk import measure,sha


def main():
    plan=json.loads((HERE/'case-plan.json').read_text())
    analysis_code=(HERE/'native/finalize.py').read_text()
    summaries=[]
    for label in ('reference','contrast'):
        case_id=f'training__C10316__NRS-484B-293__pedestrian__{label}'
        fixture=ROOT/'.runtime-work/c10316-crosswalk-synthetic'/label
        contract={
            'format':'worker-measurement-contract-v1','case_id':case_id,
            'requirements':[
                {'disposition_index':i,'requirement':item['requirement'],'source':item['source'],
                 'output_key':('right_half_passage' if i==0 else 'marked_crosswalk_passage'),
                 'method':'crosswalk_passage','value_type':'object','kind':'measured',
                 'inputs':['native_samples.jsonl','crosswalk-context.json']}
                for i,item in enumerate(plan['requirement_dispositions'])
                if item['status']=='selected_required' and case_id in item['case_ids']
            ],
            'negative':{'remove':['native_samples.jsonl'],
                        'error_contains':'Missing required source: native_samples.jsonl'}}
        contract_path=HERE/'draft-crosswalk'/label/'measurement-contract.json'
        contract_path.parent.mkdir(parents=True,exist_ok=True)
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        rows=validate(contract,plan['requirement_dispositions'],analysis_code,case_id)
        observation=measure(fixture/'native_samples.jsonl',fixture/'crosswalk-context.json')
        sources=observation['source_sha256']
        report={'measurements':{row['output_key']:{'method':'crosswalk_passage','value':observation,
                                                 'sources':sources} for row in rows}}
        verify_report(contract,report,fixture)
        missing=fixture/'does-not-exist/native_samples.jsonl'
        try:
            measure(missing,fixture/'crosswalk-context.json')
        except ValueError as exc:
            assert contract['negative']['error_contains'] in str(exc)
        else:
            raise AssertionError('Missing original source accepted')
        summaries.append({'case_id':case_id,'contract_sha256':sha(contract_path),
                          'requirements':len(rows),'positive':'passed','missing_source_negative':'rejected'})
    (HERE/'draft-crosswalk-contract-summary.json').write_text(json.dumps({
        'format':'c10316-unselected-contract-summary-v1','selected_cases':0,
        'cases':summaries},indent=2)+'\n')
    print(json.dumps({'pinned_contract_positives':2,'missing_source_negatives':2,
                      'requirements_per_case':2,'selected_cases':0},sort_keys=True))


if __name__=='__main__':
    main()
