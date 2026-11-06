"""Pinned validator positive/negative checks for unselected saved CPU drafts."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime'/'pipeline'))
sys.path.insert(0,str(HERE/'native'))
from scenario_pipeline.worker_exchange.measurement_contract import validate,verify_report  # noqa: E402
from finalize import analysis_report  # noqa: E402


def prove():
    plan=json.loads((HERE/'case-plan.json').read_text())
    code=(HERE/'native'/'finalize.py').read_text()
    records=[]
    for case in plan['cases']:
        suffix=case['case_id'].rsplit('__',1)[-1]
        contract=json.loads((HERE/'draft-measurements'/f'{suffix}-contract.json').read_text())
        validate(contract,plan['requirement_dispositions'],code,case['case_id'])
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            shutil.copy2(HERE/'draft-measurements'/'native-geometry-draft.json',folder/'road_geometry.json')
            shutil.copy2(HERE/'draft-measurements'/f'{suffix}-synthetic-native-samples.jsonl',
                         folder/'native_samples.jsonl')
            report=analysis_report(folder,contract)
            verify_report(contract,report,folder)
            (HERE/'draft-measurements'/f'{suffix}-analysis-report.json').write_text(json.dumps(report,indent=2)+'\n')
            relation=report['measurements']['after_left_turn_distance_interval']['value']['threshold_relation']
            (folder/'native_samples.jsonl').unlink()
            try: analysis_report(folder,contract)
            except ValueError as error:
                if str(error)!=contract['negative']['error_contains']:
                    raise
            else: raise AssertionError('Missing original Native samples were accepted')
            records.append({'case_id':case['case_id'],'relation':relation,
                            'positive':'passed','missing_native_samples':'rejected'})
    print(json.dumps({'status':'pinned_contract_synthetic_draft_only',
                      'selected_delivery_cases':0,'records':records},indent=2))


if __name__=='__main__':
    prove()
