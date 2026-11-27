"""Prove public saved-only positive and missing-source feedback per exact case."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT.parents[1]
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
MANIFEST=ROOT/'selected-preflight-manifest.json'
VALIDATOR=SCRATCH/'lean-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    stage=SCRATCH/('c111603-'+path.name+'.stage')
    stage.write_text(json.dumps(value,indent=2)+'\n')
    os.replace(stage,path)


def output_from_command(command):
    parts=shlex.split(command)
    return Path(parts[parts.index('--output')+1]).resolve()


def process(case,attempt,output):
    command=[sys.executable,'-B',str(REPO/'runtime.py'),'process-saved',
        '--manifest',str(MANIFEST),'--case',case,
        '--attempt',str(attempt),'--output',str(output),
        '--library',str(REPO/'runtime/library'),'--validator',str(VALIDATOR)]
    completed=subprocess.run(command,cwd=REPO,capture_output=True,text=True,
                             env=os.environ.copy(),timeout=900)
    if completed.returncode:
        raise RuntimeError(case+' saved-only failed: '+completed.stderr[-1500:])
    receipt=output/'v0001/processing.json'
    if not receipt.is_file():
        raise ValueError('Missing public saved-only receipt')
    return command,json.loads(receipt.read_text()),receipt


def one(entry,compat):
    case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
    old=json.loads((ROOT/compat['receipt']).read_text())
    if (old['construction_sha256']!=entry['construction_sha256'] or
            old['runtime_manifest_sha256']!=json.loads(MANIFEST.read_text())['runtime_manifest_sha256']):
        raise ValueError('Stale public compatibility proof: '+case)
    attempt=output_from_command(compat['command'])
    selection=json.loads((attempt/'candidate-selection.json').read_text())
    if (selection['manifest_sha256']!=sha(MANIFEST) or
            selection['construction_sha256']!=entry['construction_sha256']):
        raise ValueError('Positive fixture binds another selected manifest: '+case)
    scope=SCRATCH/('saved-'+suffix+'-'+sha(MANIFEST)[:10])
    if scope.exists():
        raise ValueError('Use fresh saved-only proof directory: '+str(scope))
    scope.mkdir()
    pc,pr,pp=process(case,attempt,scope/'positive')
    if not (pr['passed'] and pr['recorded_only'] and not pr['missing_evidence']
            and pr['originals_preserved']):
        raise ValueError('Positive saved-only receipt incomplete: '+case)
    missing=scope/'negative-attempt'
    shutil.copytree(attempt,missing,copy_function=os.link,symlinks=True)
    (missing/'intersection-context.json').unlink()
    nc,nr,np=process(case,missing,scope/'negative')
    feedback_path=scope/'negative/v0001/feedback.json'
    feedback=json.loads(feedback_path.read_text())
    if not (nr['passed'] and nr['recorded_only'] and nr['missing_evidence']
            and nr['originals_preserved'] and feedback.get('native_replay_requested') is False
            and 'intersection-context.json' in feedback.get('error','')):
        raise ValueError('Missing-source saved-only feedback incomplete: '+case)
    evidence=ROOT/'recorded-only';evidence.mkdir(exist_ok=True)
    log=evidence/(suffix+'-test.log')
    log.write_text(case+'\npositive recorded_only=true missing_evidence=false originals_preserved=true\n'
        +'negative recorded_only=true missing_evidence=true originals_preserved=true native_replay_requested=false\n'
        +'positive_receipt_sha256='+sha(pp)+'\nnegative_receipt_sha256='+sha(np)
        +'\nfeedback_sha256='+sha(feedback_path)+'\n')
    proof={'format':'worker-c111603-recorded-only-proof-v1','case_id':case,
        'construction_sha256':entry['construction_sha256'],
        'manifest_sha256':sha(MANIFEST),
        'positive_command':' '.join(pc),'negative_command':' '.join(nc),
        'positive_receipt_sha256':sha(pp),'negative_receipt_sha256':sha(np),
        'feedback_sha256':sha(feedback_path),'test_exit_code':0,
        'test_log':str(log.relative_to(ROOT)),'test_log_sha256':sha(log),
        'positive_missing_evidence':False,'negative_missing_evidence':True,
        'originals_preserved':True,'native_replay_requested':False,
        'scope':'diagnostic saved-only software fixture'}
    path=evidence/(suffix+'-proof.json');atomic(path,proof)
    return {'case_id':case,'proof':str(path.relative_to(ROOT)),
            'proof_sha256':sha(path),'construction_sha256':entry['construction_sha256'],
            'manifest_sha256':sha(MANIFEST)}


def main():
    entries=json.loads(MANIFEST.read_text())['cases']
    compatible={row['case_id']:row for row in
        json.loads((ROOT/'compatibility/index.json').read_text())['passed']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(one,entry,compatible[entry['case_id']]) for entry in entries]
        rows=[]
        for future in concurrent.futures.as_completed(futures):
            row=future.result();rows.append(row)
            print(json.dumps({'saved_only_case':row['case_id'],'proof_sha256':row['proof_sha256']}),flush=True)
    index={'format':'worker-c111603-recorded-only-index-v1',
           'passed':sorted(rows,key=lambda row:row['case_id'])}
    atomic(ROOT/'recorded-only/index.json',index)
    print(json.dumps({'saved_only_passed':len(rows),'index_sha256':sha(ROOT/'recorded-only/index.json')}))


if __name__=='__main__':
    main()
