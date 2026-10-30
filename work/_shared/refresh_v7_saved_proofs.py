"""Exercise exact saved-only positive fixtures for every selected case under v6."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PYTHON=ROOT/'.venv-cpu/bin/python'
VALIDATOR=ROOT/'.runtime-work/v7-selftest-update013/decoder/.lake/build/bin/adapterCheck'
OUTPUT=ROOT/'.runtime-work/v7-saved-case-proofs'
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v7/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
from worker_exchange.package_compatibility import materialize_case

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)

def run(item):
    folder,case_id=item;key=hashlib.sha256(case_id.encode()).hexdigest()[:16]
    work=OUTPUT/key
    if work.exists():shutil.rmtree(work)
    clone=work/'package';clone.mkdir(parents=True)
    source=json.loads((folder/'execution-manifest.json').read_text())
    entry=next(e for e in source['cases'] if e['case_id']==case_id)
    shutil.copyfile(folder/'execution-manifest.json',clone/'execution-manifest.json')
    (clone/'proposals').mkdir()
    shutil.copyfile(folder/'proposals/cases.json',clone/'proposals/cases.json')
    for candidate in [entry,*entry['candidates']]:
        path=Path(candidate['construction']);target=clone/path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(folder/path,target)
    fixture=work/'fixture';materialize(ROOT,ROOT/entry['fixture_recipe'],fixture)
    attempt=work/'attempt';materialize_case(clone/'execution-manifest.json',case_id,attempt,fixture)
    argv=[str(PYTHON),str(ROOT/'runtime.py'),'process-saved','--manifest',str(clone/'execution-manifest.json'),
          '--case',case_id,'--attempt',str(attempt),'--output',str(work/'processed'),
          '--library',str(ROOT/'runtime/main-pipeline-v7/library'),'--validator',str(VALIDATOR)]
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (work/'process-saved.log').open('w') as log:
        result=subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    if result.returncode:
        return {'case_id':case_id,'error':'process-saved','exit_code':result.returncode,'log':str(work/'process-saved.log')}
    receipt=json.loads((work/'processed/v0001/processing.json').read_text())
    if not (receipt.get('passed') is True and receipt.get('recorded_only') is True
            and receipt.get('originals_preserved') is True and receipt.get('missing_evidence') is False
            and receipt.get('candidate_id')=='primary'):
        return {'case_id':case_id,'error':'incomplete saved processing receipt','log':str(work/'process-saved.log')}
    return {'case_id':case_id,'folder':str(folder),'log':str(work/'process-saved.log'),
            'command':' '.join(argv),'receipt_sha256':sha(work/'processed/v0001/processing.json')}

def record(result):
    folder=Path(result['folder']);case_id=result['case_id']
    path=folder/'execution-manifest.json';manifest=json.loads(path.read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==case_id)
    key=hashlib.sha256(case_id.encode()).hexdigest()[:12]
    destination=folder/'receipts'/f'v7-saved-{key}.log'
    shutil.copyfile(result['log'],destination)
    post=entry['post_capture']
    post['command']=(f'python3.11 runtime.py process-saved --manifest "$LOCAL_CHECKOUT/work/{manifest["assignment_id"]}/execution-manifest.json" '
        f'--case {case_id} --attempt "$CANONICAL_ATTEMPT" --output "$PROCESSED_VERSION" '
        '--library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
    post['feedback_command']='cat "$PROCESSED_VERSION"/v*/feedback.json'
    post['test_log']=str(destination.relative_to(folder))
    post['test_log_sha256']=sha(destination);post['test_exit_code']=0
    post['v6_fixture_command']=result['command']
    post['v6_processing_receipt_sha256']=result['receipt_sha256']
    write(path,manifest)
    result_path=folder/'result.json';status=json.loads(result_path.read_text())
    status.setdefault('tests',[]).append({'command':result['command'],'exit_code':0,
        'log':post['test_log'],'sha256':post['test_log_sha256']})
    write(result_path,status)

def main():
    items=[]
    for folder in sorted((ROOT/'work').glob('testing__*')):
        p=folder/'execution-manifest.json'
        if p.is_file():
            for entry in json.loads(p.read_text())['cases']:items.append((folder,entry['case_id']))
    done=0;failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,item) for item in items]):
            result=future.result()
            if 'error' in result:failures.append(result)
            else:record(result);done+=1
            if (done+len(failures))%20==0:print(json.dumps({'completed':done,'failures':len(failures),'total':len(items)}),flush=True)
    write(ROOT/'work/_shared/v7-saved-proof-failures.json',failures)
    print(json.dumps({'completed':done,'failures':failures,'total':len(items)}),flush=True)
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
