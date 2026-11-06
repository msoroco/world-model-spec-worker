"""Exercise each exact C104538 contract on a distinct synthetic saved identity."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def run():
    summary=json.loads((ROOT/'pinned-contract-summary.json').read_text())
    source=REPO/'.runtime-work/c104538/draft-saved-v4/base'
    parent=REPO/'.runtime-work/c104538/pinned-contract-probes-v1'
    if parent.exists():raise ValueError('Retain prior case probes; choose a new version')
    env=dict(os.environ)
    env['PATH']=str(REPO/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['PYTHONPATH']=os.pathsep.join([str(REPO/'runtime/pipeline/scenario_pipeline'),
                                     str(ROOT/'native'),env.get('PYTHONPATH','')])
    rows=[]
    for item in summary['cases']:
        case_id=item['case_id'];suffix=case_id.split('__')[-1]
        contract=json.loads((ROOT/item['contract']).read_text())
        case_root=parent/suffix
        positive=case_root/'positive';shutil.copytree(source,positive)
        for relative in ('config.json','native-construction-context.json','capture/manifest.json'):
            path=positive/relative;data=json.loads(path.read_text());data['case_id']=case_id
            if relative=='config.json':data['case_suffix']=suffix
            write(path,data)
        negative=case_root/'negative_missing_body';shutil.copytree(positive,negative)
        (negative/'native_body_history.jsonl').unlink()
        entry=ROOT/'native/finalize.py'
        receipts=[]
        for label,attempt in (('positive',positive),('negative_missing_body',negative)):
            result=subprocess.run(['python3.11',str(entry),'--attempt',str(attempt),
                '--output',str(attempt/'analysis-report.json')],
                capture_output=True,text=True,env=env,timeout=120)
            log=ROOT/'pinned-contract-logs'/suffix/(label+'.log')
            log.parent.mkdir(parents=True,exist_ok=True)
            log.write_text(result.stdout+result.stderr)
            if label=='positive':
                assert result.returncode==0,(case_id,result.stderr)
                report=json.loads((positive/'analysis-report.json').read_text())
                assert report['case_id']==case_id
                values=verify_report(contract,report,positive)
                assert len(values)==4
            else:
                assert result.returncode!=0 and contract['negative']['error_contains'] in result.stderr
            receipts.append({'label':label,'exit_code':result.returncode,
                'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)})
        rows.append({'case_id':case_id,'case_suffix':suffix,
            'positive_report_sha256':sha(positive/'analysis-report.json'),
            'positive_result_sha256':sha(positive/'result.json'),
            'contract_sha256':sha(ROOT/item['contract']),'receipts':receipts})
    output={'format':'c104538-all-case-synthetic-contract-proof-v1','cases':rows,
        'positive_saved_value_count':3,'negative_missing_body_count':3,
        'original_native_measurement_count':0,'selected_case_count':0,
        'scope':'three-frame synthetic exact-identity contract values; no physical or 480-frame package proof'}
    write(ROOT/'pinned-contract-saved-summary.json',output)
    return {'positives':3,'negatives':3,'native_measurements':0}


if __name__=='__main__':print(json.dumps(run()))
