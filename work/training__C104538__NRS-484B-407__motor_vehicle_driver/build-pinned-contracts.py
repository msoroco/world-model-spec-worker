"""Bind C104538 selected-required rows to the saved diagnostic finalizer."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from finalize import MEASUREMENT_INPUTS
from worker_exchange.measurement_contract import validate,verify_report


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    code=(ROOT/'native/finalize.py').read_text()
    keys=list(MEASUREMENT_INPUTS)
    case_rows=[]
    for case in plan['cases']:
        case_id=case['case_id']
        requirements=[]
        for index,disposition in enumerate(plan['requirement_dispositions']):
            if disposition['status']!='selected_required' or case_id not in disposition.get('case_ids',[]):
                continue
            key=keys[index]
            requirements.append({'disposition_index':index,
                'requirement':disposition['requirement'],'source':disposition['source'],
                'output_key':key,'method':'measure_case_sources',
                'value_type':'object','kind':'measured','inputs':list(MEASUREMENT_INPUTS[key])})
        contract={'format':'worker-measurement-contract-v1','case_id':case_id,
            'requirements':requirements,
            'negative':{'remove':['native_body_history.jsonl'],
                        'error_contains':'Missing required source: native_body_history.jsonl'}}
        path=ROOT/'draft-candidates'/case_id.split('__')[-1]/'measurement-contract.json'
        path.write_text(json.dumps(contract,indent=2)+'\n')
        validate(contract,plan['requirement_dispositions'],code,case_id)
        case_rows.append({'case_id':case_id,'contract':str(path.relative_to(ROOT)),
                          'contract_sha256':sha(path),'pinned_valid':True,
                          'synthetic_saved_values_verified':False})
    fixture=REPO/'.runtime-work/c104538/draft-saved-v4/positive'
    positive=json.loads((fixture/'analysis-report.json').read_text())
    first_contract=json.loads((ROOT/case_rows[0]['contract']).read_text())
    verified=verify_report(first_contract,positive,fixture)
    case_rows[0]['synthetic_saved_values_verified']=True
    negative=REPO/'.runtime-work/c104538/draft-saved-v4/negative_missing_body'
    if negative.exists():raise ValueError('Retain prior negative; use a fresh diagnostic')
    shutil.copytree(REPO/'.runtime-work/c104538/draft-saved-v4/base',negative)
    (negative/'native_body_history.jsonl').unlink()
    env={'PATH':str(REPO/'.runtime-work/linux_arm64')+':'+__import__('os').environ.get('PATH',''),
         'PYTHONPATH':str(REPO/'runtime/pipeline/scenario_pipeline')+':'+str(ROOT/'native')}
    result=subprocess.run(['python3.11',str(ROOT/'native/finalize.py'),
        '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
        capture_output=True,text=True,env=env,timeout=120)
    log=ROOT/'pinned-contract-negative.log';log.write_text(result.stdout+result.stderr)
    assert result.returncode!=0 and first_contract['negative']['error_contains'] in result.stderr
    summary={'format':'c104538-pinned-contract-diagnostic-v1','cases':case_rows,
        'pinned_validator_pass_count':len(case_rows),
        'synthetic_saved_value_pass_count':1,
        'saved_value_output_keys':sorted(verified),
        'missing_body_negative_exit_code':result.returncode,
        'missing_body_negative_log_sha256':sha(log),
        'original_native_measurements_verified':0,
        'scope':'pinned schema and one three-frame synthetic saved value; no physical visibility proof'}
    (ROOT/'pinned-contract-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return {'validated':len(case_rows),'synthetic_values':1,'negative_rejected':True}


if __name__=='__main__':print(json.dumps(build()))
