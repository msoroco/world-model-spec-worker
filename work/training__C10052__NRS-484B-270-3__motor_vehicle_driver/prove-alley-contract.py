"""Validate the draft alley measurement contract against executable saved output."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.measurement_contract import validate,verify_report


def prove():
    contract = json.loads((HERE/'draft-alley-measurement-contract.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    dispositions = [dict(row) for row in plan['requirement_dispositions']]
    dispositions[0]['case_ids'] = [*dispositions[0]['case_ids'],contract['case_id']]
    code = (HERE/'native/finalize_alley.py').read_text()
    validate(contract,dispositions,code,contract['case_id'])
    summary = json.loads((HERE/'alley-saved-summary.json').read_text())
    fixture = REPO/summary['source_root']/'positive'
    report = json.loads((fixture/'analysis-report.json').read_text())
    measured = verify_report(contract,report,fixture)
    value = measured['alley_transition_observation']['value']
    assert value['simultaneous_moving_overlap_frames'] == 27
    assert value['statutory_exception_observed'] == 'unresolved'
    return {'format':'c10052-alley-draft-contract-proof-v1',
            'case_id':contract['case_id'],'measurement_keys':list(measured),
            'simultaneous_moving_overlap_frames':27,
            'plan_case_ids_extension':'local draft only; main case plan not selected',
            'selected':False,'accepted':False}


if __name__=='__main__':
    print(json.dumps(prove(),indent=2))
